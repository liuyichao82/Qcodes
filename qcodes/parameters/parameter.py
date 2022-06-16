# TODO (alexcjohnson) update this with the real duck-typing requirements or
# create an ABC for Parameter and MultiParameter - or just remove this statement
# if everyone is happy to use these classes.

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Sequence, Union, cast

from typing_extensions import Literal

from qcodes.utils.command import Command
from qcodes.utils.validators import Validator

from .parameter_base import ParamDataType, ParameterBase, ParamRawDataType
from .sweep_values import SweepFixedValues

if TYPE_CHECKING:
    from qcodes.instrument.base import InstrumentBase


log = logging.getLogger(__name__)


class Parameter(ParameterBase):
    """
    A parameter represents a single degree of freedom. Most often,
    this is the standard parameter for Instruments, though it can also be
    used as a variable, i.e. storing/retrieving a value, or be subclassed for
    more complex uses.

    By default only gettable, returning its last value.
    This behaviour can be modified in two ways:

    1. Providing a ``get_cmd``/``set_cmd``, which can do the following:

       a. callable, with zero args for get_cmd, one arg for set_cmd
       b. VISA command string
       c. None, in which case it retrieves its last value for ``get_cmd``,
          and stores a value for ``set_cmd``
       d. False, in which case trying to get/set will raise an error.

    2. Creating a subclass with an explicit :meth:`get_raw`/:meth:`set_raw`
       method.

       This enables more advanced functionality. The :meth:`get_raw` and
       :meth:`set_raw` methods are automatically wrapped to provide ``get`` and
       ``set``.

    It is an error to do both 1 and 2. E.g supply a ``get_cmd``/``set_cmd``
    and implement ``get_raw``/``set_raw``


    To detect if a parameter is gettable or settable check the attributes
    :py:attr:`~gettable` and :py:attr:`~settable` on the parameter.

    Parameters have a ``cache`` object that stores internally the current
    ``value`` and ``raw_value`` of the parameter. Calling ``cache.get()``
    (or ``cache()``) simply returns the most recent set or measured value of
    the parameter.

    Parameter also has a ``.get_latest`` method that duplicates the behavior
    of ``cache()`` call, as in, it also simply returns the most recent set
    or measured value.

    Args:
        name: The local name of the parameter. Should be a valid
            identifier, ie no spaces or special characters. If this parameter
            is part of an Instrument or Station, this is how it will be
            referenced from that parent, ie ``instrument.name`` or
            ``instrument.parameters[name]``.

        instrument: The instrument this parameter
            belongs to, if any.

        label: Normally used as the axis label when this
            parameter is graphed, along with ``unit``.

        unit: The unit of measure. Use ``''`` for unitless.

        snapshot_get: ``False`` prevents any update to the
            parameter during a snapshot, even if the snapshot was called with
            ``update=True``, for example, if it takes too long to update,
            or if the parameter is only meant for measurements hence calling
            get on it during snapshot may be an error. Default True.

        snapshot_value: ``False`` prevents parameter value to be
            stored in the snapshot. Useful if the value is large.

        snapshot_exclude: ``True`` prevents parameter to be
            included in the snapshot. Useful if there are many of the same
            parameter which are clogging up the snapshot.
            Default ``False``.

        step: Max increment of parameter value.
            Larger changes are broken into multiple steps this size.
            When combined with delays, this acts as a ramp.

        scale: Scale to multiply value with before
            performing set. the internally multiplied value is stored in
            ``cache.raw_value``. Can account for a voltage divider.

        inter_delay: Minimum time (in seconds)
            between successive sets. If the previous set was less than this,
            it will wait until the condition is met.
            Can be set to 0 to go maximum speed with no errors.

        post_delay: Time (in seconds) to wait
            after the *start* of each set, whether part of a sweep or not.
            Can be set to 0 to go maximum speed with no errors.

        val_mapping: A bi-directional map data/readable values
            to instrument codes, expressed as a dict:
            ``{data_val: instrument_code}``
            For example, if the instrument uses '0' to mean 1V and '1' to mean
            10V, set val_mapping={1: '0', 10: '1'} and on the user side you
            only see 1 and 10, never the coded '0' and '1'
            If vals is omitted, will also construct a matching Enum validator.
            **NOTE** only applies to get if get_cmd is a string, and to set if
            set_cmd is a string.
            You can use ``val_mapping`` with ``get_parser``, in which case
            ``get_parser`` acts on the return value from the instrument first,
            then ``val_mapping`` is applied (in reverse).

        get_parser: Function to transform the response
            from get to the final output value. See also `val_mapping`.

        set_parser: Function to transform the input set
            value to an encoded value sent to the instrument.
            See also `val_mapping`.

        vals: Allowed values for setting this parameter.
            Only relevant if settable. Defaults to ``Numbers()``.

        max_val_age: The max time (in seconds) to trust a
            saved value obtained from ``cache()`` (or ``cache.get()``, or
            ``get_latest()``. If this parameter has not been set or measured
            more recently than this, perform an additional measurement.

        initial_value: Value to set the parameter to at the end of its
            initialization (this is equivalent to calling
            ``parameter.set(initial_value)`` after parameter initialization).
            Cannot be passed together with ``initial_cache_value`` argument.

        initial_cache_value: Value to set the cache of the parameter to
            at the end of its initialization (this is equivalent to calling
            ``parameter.cache.set(initial_cache_value)`` after parameter
            initialization). Cannot be passed together with ``initial_value``
            argument.

        docstring: Documentation string for the ``__doc__``
            field of the object. The ``__doc__``  field of the instance is
            used by some help systems, but not all.

        metadata: Extra information to include with the
            JSON snapshot of the parameter.

        abstract: Specifies if this parameter is abstract or not. Default
            is False. If the parameter is 'abstract', it *must* be overridden
            by a non-abstract parameter before the instrument containing
            this parameter can be instantiated. We override a parameter by
            adding one with the same name and unit. An abstract parameter
            can be added in a base class and overridden in a subclass.

        bind_to_instrument: Should the parameter be registered as a delegate attribute
            on the instrument passed via the instrument argument.
    """

    def __init__(
        self,
        name: str,
        instrument: Optional["InstrumentBase"] = None,
        label: Optional[str] = None,
        unit: Optional[str] = None,
        get_cmd: Optional[Union[str, Callable[..., Any], Literal[False]]] = None,
        set_cmd: Optional[Union[str, Callable[..., Any], Literal[False]]] = False,
        initial_value: Optional[Union[float, str]] = None,
        max_val_age: Optional[float] = None,
        vals: Optional[Validator[Any]] = None,
        docstring: Optional[str] = None,
        initial_cache_value: Optional[Union[float, str]] = None,
        bind_to_instrument: bool = True,
        **kwargs: Any,
    ) -> None:
        if instrument is not None and bind_to_instrument:
            existing_parameter = instrument.parameters.get(name, None)

            if existing_parameter:

                # this check is redundant since its also in the baseclass
                # but if we do not put it here it would be an api break
                # as parameter duplication check won't be done first,
                # hence for parameters that are duplicates and have
                # wrong units, users will be getting ValueError where
                # they used to have KeyError before.
                if not existing_parameter.abstract:
                    raise KeyError(
                        f"Duplicate parameter name {name} on instrument {instrument}"
                    )

                existing_unit = getattr(existing_parameter, "unit", None)
                if existing_unit != unit:
                    raise ValueError(
                        f"The unit of the parameter '{name}' is '{unit}'. "
                        f"This is inconsistent with the unit defined in the "
                        f"base class"
                    )

        super().__init__(
            name=name,
            instrument=instrument,
            vals=vals,
            max_val_age=max_val_age,
            bind_to_instrument=bind_to_instrument,
            **kwargs,
        )

        no_instrument_get = not self.gettable and (get_cmd is None or get_cmd is False)
        # TODO: a matching check should be in ParameterBase but
        #   due to the current limited design the ParameterBase cannot
        #   know if this subclass will supply a get_cmd
        #   To work around this a RunTime check is put into get of GetLatest
        #   and into get of _Cache
        if max_val_age is not None and no_instrument_get:
            raise SyntaxError(
                "Must have get method or specify get_cmd when max_val_age is set"
            )

        # Enable set/get methods from get_cmd/set_cmd if given and
        # no `get`/`set` or `get_raw`/`set_raw` methods have been defined
        # in the scope of this class.
        # (previous call to `super().__init__` wraps existing
        # get_raw/set_raw into get/set methods)
        if self.gettable and get_cmd not in (None, False):
            raise TypeError(
                "Supplying a not None or False `get_cmd` to a Parameter"
                " that already implements"
                " get_raw is an error."
            )
        elif not self.gettable and get_cmd is not False:
            if get_cmd is None:
                self.get_raw = lambda: self.cache.raw_value  # type: ignore[assignment]
            else:
                if isinstance(get_cmd, str) and instrument is None:
                    raise TypeError(
                        f"Cannot use a str get_cmd without "
                        f"binding to an instrument. "
                        f"Got: get_cmd {get_cmd} for parameter {name}"
                    )

                exec_str_ask = getattr(instrument, "ask", None) if instrument else None

                self.get_raw = Command(  # type: ignore[assignment]
                    arg_count=0,
                    cmd=get_cmd,
                    exec_str=exec_str_ask,
                )
            self._gettable = True
            self.get = self._wrap_get(self.get_raw)

        if self.settable and set_cmd not in (None, False):
            raise TypeError(
                "Supplying a not None or False `set_cmd` to a Parameter"
                " that already implements"
                " set_raw is an error."
            )
        elif not self.settable and set_cmd is not False:
            if set_cmd is None:
                self.set_raw: Callable[..., Any] = lambda x: x
            else:
                if isinstance(set_cmd, str) and instrument is None:
                    raise TypeError(
                        f"Cannot use a str set_cmd without "
                        f"binding to an instrument. "
                        f"Got: set_cmd {set_cmd} for parameter {name}"
                    )

                exec_str_write = (
                    getattr(instrument, "write", None) if instrument else None
                )
                self.set_raw = Command(
                    arg_count=1, cmd=set_cmd, exec_str=exec_str_write
                )
            self._settable = True
            self.set = self._wrap_set(self.set_raw)

        self._meta_attrs.extend(["label", "unit", "vals"])

        self.label = name if label is None else label
        self._label: str

        self.unit = unit if unit is not None else ""
        self._unitval: str

        if initial_value is not None and initial_cache_value is not None:
            raise SyntaxError(
                "It is not possible to specify both of the "
                "`initial_value` and `initial_cache_value` "
                "keyword arguments."
            )

        if initial_value is not None:
            self.set(initial_value)

        if initial_cache_value is not None:
            self.cache.set(initial_cache_value)

        # generate default docstring
        self.__doc__ = os.linesep.join(
            (
                "Parameter class:",
                "",
                "* `name` %s" % self.name,
                "* `label` %s" % self.label,
                "* `unit` %s" % self.unit,
                "* `vals` %s" % repr(self.vals),
            )
        )

        if docstring is not None:
            self.__doc__ = os.linesep.join((docstring, "", self.__doc__))

    @property
    def unit(self) -> str:
        """
        The unit of measure. Use ``''`` (the empty string)
        for unitless.
        """
        return self._unitval

    @unit.setter
    def unit(self, unit: str) -> None:
        self._unitval = unit

    @property
    def label(self) -> str:
        """
        Label of the data used for plots etc.
        """
        return self._label

    @label.setter
    def label(self, label: str) -> None:
        self._label = label

    def __getitem__(self, keys: Any) -> "SweepFixedValues":
        """
        Slice a Parameter to get a SweepValues object
        to iterate over during a sweep
        """
        return SweepFixedValues(self, keys)

    def increment(self, value: ParamDataType) -> None:
        """Increment the parameter with a value

        Args:
            value: Value to be added to the parameter.
        """
        self.set(self.get() + value)

    def sweep(
        self,
        start: float,
        stop: float,
        step: Optional[float] = None,
        num: Optional[int] = None,
    ) -> SweepFixedValues:
        """
        Create a collection of parameter values to be iterated over.
        Requires `start` and `stop` and (`step` or `num`)
        The sign of `step` is not relevant.

        Args:
            start: The starting value of the sequence.
            stop: The end value of the sequence.
            step:  Spacing between values.
            num: Number of values to generate.

        Returns:
            SweepFixedValues: Collection of parameter values to be
            iterated over.

        Examples:
            >>> sweep(0, 10, num=5)
             [0.0, 2.5, 5.0, 7.5, 10.0]
            >>> sweep(5, 10, step=1)
            [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
            >>> sweep(15, 10.5, step=1.5)
            >[15.0, 13.5, 12.0, 10.5]
        """
        return SweepFixedValues(self, start=start, stop=stop, step=step, num=num)


class DelegateParameter(Parameter):
    """
    The :class:`.DelegateParameter` wraps a given `source` :class:`Parameter`.
    Setting/getting it results in a set/get of the source parameter with
    the provided arguments.

    The reason for using a :class:`DelegateParameter` instead of the
    source parameter is to provide all the functionality of the Parameter
    base class without overwriting properties of the source: for example to
    set a different scaling factor and unit on the :class:`.DelegateParameter`
    without changing those in the source parameter.

    The :class:`DelegateParameter` supports changing the `source`
    :class:`Parameter`. :py:attr:`~gettable`, :py:attr:`~settable` and
    :py:attr:`snapshot_value` properties automatically follow the source
    parameter. If source is set to ``None`` :py:attr:`~gettable` and
    :py:attr:`~settable` will always be ``False``. It is therefore an error
    to call get and set on a :class:`DelegateParameter` without a `source`.
    Note that a parameter without a source can be snapshotted correctly.

    :py:attr:`.unit` and :py:attr:`.label` can either be set when constructing
    a :class:`DelegateParameter` or inherited from the source
    :class:`Parameter`. If inherited they will automatically change when
    changing the source. Otherwise they will remain fixed.

    Note:
        DelegateParameter only supports mappings between the
        :class:`.DelegateParameter` and :class:`.Parameter` that are invertible
        (e.g. a bijection). It is therefor not allowed to create a
        :class:`.DelegateParameter` that performs non invertible
        transforms in its ``get_raw`` method.

        A DelegateParameter is not registered on the instrument by default.
        You should pass ``bind_to_instrument=True`` if you want this to
        be the case.
    """

    class _DelegateCache:
        def __init__(self, parameter: "DelegateParameter"):
            self._parameter = parameter
            self._marked_valid: bool = False

        @property
        def raw_value(self) -> ParamRawDataType:
            """
            raw_value is an attribute that surfaces the raw value from the
            cache. In the case of a :class:`DelegateParameter` it reflects
            the value of the cache of the source.

            Strictly speaking it should represent that value independent of
            its validity according to the `max_val_age` but in fact it does
            lose its validity when the maximum value age has been reached.
            This bug will not be fixed since the `raw_value` property will be
            removed soon.
            """
            if self._parameter.source is None:
                raise TypeError(
                    "Cannot get the raw value of a "
                    "DelegateParameter that delegates to None"
                )
            return self._parameter.source.cache.get(get_if_invalid=False)

        @property
        def max_val_age(self) -> Optional[float]:
            if self._parameter.source is None:
                return None
            return self._parameter.source.cache.max_val_age

        @property
        def timestamp(self) -> Optional[datetime]:
            if self._parameter.source is None:
                return None
            return self._parameter.source.cache.timestamp

        @property
        def valid(self) -> bool:
            if self._parameter.source is None:
                return False
            source_cache = self._parameter.source.cache
            return source_cache.valid

        def invalidate(self) -> None:
            if self._parameter.source is not None:
                self._parameter.source.cache.invalidate()

        def get(self, get_if_invalid: bool = True) -> ParamDataType:
            if self._parameter.source is None:
                raise TypeError(
                    "Cannot get the cache of a "
                    "DelegateParameter that delegates to None"
                )
            return self._parameter._from_raw_value_to_value(
                self._parameter.source.cache.get(get_if_invalid=get_if_invalid)
            )

        def set(self, value: ParamDataType) -> None:
            if self._parameter.source is None:
                raise TypeError(
                    "Cannot set the cache of a DelegateParameter "
                    "that delegates to None"
                )
            self._parameter.validate(value)
            self._parameter.source.cache.set(
                self._parameter._from_value_to_raw_value(value)
            )

        def _set_from_raw_value(self, value: ParamRawDataType) -> None:
            if self._parameter.source is None:
                raise TypeError(
                    "Cannot set the cache of a DelegateParameter "
                    "that delegates to None"
                )
            self._parameter.source.cache.set(value)

        def _update_with(
            self,
            *,
            value: ParamDataType,
            raw_value: ParamRawDataType,
            timestamp: Optional[datetime] = None,
        ) -> None:
            """
            This method is needed for interface consistency with ``._Cache``
            because it is used by ``ParameterBase`` in
            ``_wrap_get``/``_wrap_set``. Due to the fact that the source
            parameter already maintains it's own cache and the cache of the
            delegate parameter mirrors the cache of the source parameter by
            design, this method is just a noop.
            """
            pass

        def __call__(self) -> ParamDataType:
            return self.get(get_if_invalid=True)

    def __init__(
        self,
        name: str,
        source: Optional[Parameter],
        *args: Any,
        **kwargs: Any,
    ):
        if "bind_to_instrument" not in kwargs.keys():
            kwargs["bind_to_instrument"] = False

        self._attr_inherit = {
            "label": {"fixed": False, "value_when_without_source": name},
            "unit": {"fixed": False, "value_when_without_source": ""},
        }

        for attr, attr_props in self._attr_inherit.items():
            if attr in kwargs:
                attr_props["fixed"] = True
            else:
                attr_props["fixed"] = False
            source_attr = getattr(source, attr, attr_props["value_when_without_source"])
            kwargs[attr] = kwargs.get(attr, source_attr)

        for cmd in ("set_cmd", "get_cmd"):
            if cmd in kwargs:
                raise KeyError(
                    f'It is not allowed to set "{cmd}" of a '
                    f"DelegateParameter because the one of the "
                    f"source parameter is supposed to be used."
                )
        if source is None and (
            "initial_cache_value" in kwargs or "initial_value" in kwargs
        ):
            raise KeyError(
                "It is not allowed to supply 'initial_value'"
                " or 'initial_cache_value' "
                "without a source."
            )

        initial_cache_value = kwargs.pop("initial_cache_value", None)
        self.source = source
        super().__init__(name, *args, **kwargs)
        # explicitly set the source properties as
        # init will overwrite the ones set when assigning source
        self._set_properties_from_source(source)

        self.cache = self._DelegateCache(self)
        if initial_cache_value is not None:
            self.cache.set(initial_cache_value)

    @property
    def source(self) -> Optional[Parameter]:
        """
        The source parameter that this :class:`DelegateParameter` is bound to
        or ``None`` if this  :class:`DelegateParameter` is unbound.

        :getter: Returns the current source.
        :setter: Sets the source.
        """
        return self._source

    @source.setter
    def source(self, source: Optional[Parameter]) -> None:
        self._set_properties_from_source(source)
        self._source: Optional[Parameter] = source

    def _set_properties_from_source(self, source: Optional[Parameter]) -> None:
        if source is None:
            self._gettable = False
            self._settable = False
            self._snapshot_value = False
        else:
            self._gettable = source.gettable
            self._settable = source.settable
            self._snapshot_value = source._snapshot_value

        for attr, attr_props in self._attr_inherit.items():
            if not attr_props["fixed"]:
                attr_val = getattr(
                    source, attr, attr_props["value_when_without_source"]
                )
                setattr(self, attr, attr_val)

    # pylint: disable=method-hidden
    def get_raw(self) -> Any:
        if self.source is None:
            raise TypeError(
                "Cannot get the value of a DelegateParameter "
                "that delegates to a None source."
            )
        return self.source.get()

    # pylint: disable=method-hidden
    def set_raw(self, value: Any) -> None:
        if self.source is None:
            raise TypeError(
                "Cannot set the value of a DelegateParameter "
                "that delegates to a None source."
            )
        self.source(value)

    def snapshot_base(
        self,
        update: Optional[bool] = True,
        params_to_skip_update: Optional[Sequence[str]] = None,
    ) -> Dict[Any, Any]:
        snapshot = super().snapshot_base(
            update=update, params_to_skip_update=params_to_skip_update
        )
        source_parameter_snapshot = (
            None if self.source is None else self.source.snapshot(update=update)
        )
        snapshot.update({"source_parameter": source_parameter_snapshot})
        return snapshot


class ManualParameter(Parameter):
    def __init__(
        self,
        name: str,
        instrument: Optional["InstrumentBase"] = None,
        initial_value: Any = None,
        **kwargs: Any,
    ):
        """
        A simple alias for a parameter that does not have a set or
        a get function. Useful for parameters that do not have a direct
        instrument mapping.
        """
        super().__init__(
            name=name,
            instrument=instrument,
            get_cmd=None,
            set_cmd=None,
            initial_value=initial_value,
            **kwargs,
        )
