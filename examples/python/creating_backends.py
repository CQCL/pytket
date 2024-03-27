# # How to create your own `Backend` using `pytket`

# In this tutorial, we will focus on:
# - the components of the abstract `Backend` class;
# - adaptations for statevector simulation versus measurement sampling.

# To run this example, you will only need the core `pytket` package.
#
# The `pytket` framework currently has direct integration with the largest variety of devices and simulators out of any quantum software platform, but this is certainly not a complete collection. New quantum backends are frequently being rolled out as more device manufacturers bring their machines online and advanced in simulation research give rise to many purpose-built simulators for fast execution of specific circuit fragments.
#
# If you have something that can take circuits (i.e. a sequence of gates) and run/simulate them, adding integration with `pytket` connects it to a great number of users and enables existing software solutions to immediately take advantage of your new backend. This reach is further extended beyond just software written with `pytket` by exploiting its integration with the rest of the quantum software ecosystem, such as via the `TketBackend` wrapper to use the new backend within Qiskit projects.
#
# This notebook will take a toy simulator and demonstrate how to write each component of the `Backend` class to make it work with the rest of `pytket`. We'll start by defining the internal representation of a circuit that our simulator will use. Rather than common gates, this example will use exponentiated Pauli tensors ($e^{-i \theta P}$ for $P \in \{I, X, Y, Z\}^n$) as its basic operation, which are universal for unitary circuits. To keep it simple, we will ignore measurements for now and just consider unitaries.

from pytket import Qubit
from pytket.pauli import QubitPauliString
from typing import List


class MyCircuit:
    """A minimal representation of a unitary circuit"""

    def __init__(self, qubits: List[Qubit]):
        """Creates a circuit over some set of qubits

        :param qubits: The list of qubits in the circuit
        :type qubits: List[Qubit]
        """
        self.qubits = sorted(qubits, reverse=True)
        self.gates = list()

    def add_gate(self, qps: QubitPauliString, angle: float):
        """Adds a gate to the end of the circuit e^{-0.5i * qps * angle}

        :param qps: Pauli string to rotate around
        :type qps: QubitPauliString
        :param angle: Angle of rotation in radians
        :type angle: float
        """
        self.gates.append((qps, angle))


# To simulate these, it is enough to generate the matrix of these exponentials and apply them in sequence to our initial state. Calculating these matrix exponentials is easy since we can exploit the following property: if an operator $A$ satisfies $A^2 = I$, then $e^{i\theta A} = \mathrm{cos}(\theta)I + i \mathrm{sin}(\theta) A$. This works for any tensor of Pauli matrices. Furthermore, since each Pauli matrix is some combination of a diagonal matrix and a permutation matrix, they benefit greatly from a sparse matrix representation, which we can obtain from the `QubitPauliString`.

import numpy as np


class MySimulator:
    """A minimal statevector simulator for unitary circuits"""

    def __init__(self, qubits: List[Qubit]):
        """Initialise a statevector, setting all qubits to the |0❭ state.
        We treat qubits[0] as the most-significant qubit

        :param qubits: The list of qubits in the circuit
        :type qubits: List[Qubit]
        """
        self._qubits = qubits
        self._qstate = np.zeros((2 ** len(qubits),), dtype=complex)
        self._qstate[0] = 1.0

    def apply_Pauli_rot(self, qps: QubitPauliString, angle: float):
        """Applies e^{-0.5i * qps * angle} to the state

        :param qps: Pauli to rotate around
        :type qps: QubitPauliString
        :param angle: Angle of rotation in radians
        :type angle: float
        """
        pauli_tensor = qps.to_sparse_matrix(self._qubits)
        exponent = -0.5 * angle
        self._qstate = np.cos(exponent) * self._qstate + 1j * np.sin(
            exponent
        ) * pauli_tensor.dot(self._qstate)


def run_mycircuit(circ: MyCircuit) -> np.ndarray:
    """Gives the state after applying the circuit to the all-|0❭ state

    :param circ: The circuit to simulate
    :type circ: MyCircuit
    :return: The final statevector
    :rtype: np.ndarray
    """
    sim = MySimulator(circ.qubits)
    for qps, angle in circ.gates:
        sim.apply_Pauli_rot(qps, angle)
    return sim._qstate


# And that's all we need for a basic simulator! We can check that this works by trying to generate a Bell state (up to global phase).

from pytket.pauli import Pauli

q = [Qubit(0), Qubit(1)]
circ = MyCircuit(q)
# Hadamard on Qubit(0)
circ.add_gate(QubitPauliString(Qubit(0), Pauli.Z), np.pi / 2)
circ.add_gate(QubitPauliString(Qubit(0), Pauli.X), np.pi / 2)
circ.add_gate(QubitPauliString(Qubit(0), Pauli.Z), np.pi / 2)
# CX with control Qubit(0) and target Qubit(1)
circ.add_gate(QubitPauliString(Qubit(0), Pauli.Z), -np.pi / 2)
circ.add_gate(QubitPauliString(Qubit(1), Pauli.X), -np.pi / 2)
circ.add_gate(QubitPauliString({Qubit(0): Pauli.Z, Qubit(1): Pauli.X}), np.pi / 2)
print(run_mycircuit(circ))

# A useful first step to integrating this is to define a conversion from the `pytket.Circuit` class to the `MyCircuit` class. In most cases, this will just amount to converting one gate at a time by a simple syntax map. We need not specify how to convert every possible `OpType`, since we can rely on the compilation passes in `pytket` to map the circuit into the required gate set as long as it is universal. For this example, the definitions of `OpType.Rx`, `OpType.Ry`, `OpType.Rz`, and `OpType.ZZMax` all match the form of a single Pauli exponential.

from pytket import Circuit, OpType


def tk_to_mycircuit(tkc: Circuit) -> MyCircuit:
    """Convert a pytket Circuit to a MyCircuit object.
    Supports Rz, Rx, Ry, and ZZMax gates.

    :param tkc: The Circuit to convert
    :type tkc: Circuit
    :return: An equivalent MyCircuit object
    :rtype: MyCircuit
    """
    circ = MyCircuit(tkc.qubits)
    for command in tkc:
        optype = command.op.type
        if optype == OpType.Rx:
            circ.add_gate(
                QubitPauliString(command.args[0], Pauli.X), np.pi * command.op.params[0]
            )
        elif optype == OpType.Ry:
            circ.add_gate(
                QubitPauliString(command.args[0], Pauli.Y), np.pi * command.op.params[0]
            )
        elif optype == OpType.Rz:
            circ.add_gate(
                QubitPauliString(command.args[0], Pauli.Z), np.pi * command.op.params[0]
            )
        elif optype == OpType.ZZMax:
            circ.add_gate(
                QubitPauliString(command.args, [Pauli.Z, Pauli.Z]), np.pi * 0.5
            )
        else:
            raise ValueError("Cannot convert optype to MyCircuit: ", optype)
    return circ


# Now we turn to the `Backend` class. This provides a uniform API to submit `Circuit` objects for evaluation, typically returning either a statevector or a set of measurement shots. It also captures all of the information needed for compilation and asynchronous job management.
#
# We will make a subclass of `Backend` for our statevector simulator. The `_supports_state` flag lets the methods of the abstract `Backend` class know that this implementation supports statevector simulation. We also set `_persistent_handles` to `False` since this `Backend` will not be able to retrieve results from a previous Python session.
#
# Since we do not need to connect to a remote process for the simulator, the constructor doesn't need to set anything up. The base `Backend` constructor will initialise the `_cache` field for storing job data.

from pytket.backends import Backend


class MyBackend(Backend):
    """A pytket Backend wrapping around the MySimulator statevector simulator"""

    _supports_state = True
    _persistent_handles = False

    def __init__(self):
        """Create a new instance of the MyBackend class"""
        super().__init__()


# Most `Backend`s will only support a small fragment of the `Circuit` language, either through implementation limitations or since a specific presentation is universal. It is helpful to keep this information in the `Backend` object itself so that users can clearly see how a `Circuit` needs to look before it can be successfully run. The `Predicate` classes in `pytket` can capture many common restrictions. The idea behind the `required_predicates` list is that any `Circuit` satisfying every `Predicate` in the list can be run on the `Backend` successfully as it is.
#
# However, a typical high-level user will not be writing `Circuit`s that satisfies all of the `required_predicates`, preferring instead to use the model that is most natural for the algorithm they are implementing. Providing a `default_compilation_pass` gives users an easy starting point for compiling an arbitrary `Circuit` into a form that can be executed (when not blocked by paradigm constraints like `NoMidMeasurePredicate` or `NoClassicalControlPredicate` that cannot easily be solved by compilation).
#
# You can provide several options using the `optimisation_level` argument. We tend to use `0` for very basic compilation with no optimisation applied, `1` for the inclusion of fast optimisations (e.g. `SynthesiseIBM` is a pre-defined sequence of optimisation passes that scales well with circuit size), and `2` for heavier optimisation (e.g. `FullPeepholeOptimise` incorporates `SynthesiseTket` alongside some extra passes that may take longer for large circuits).
#
# When designing these compilation pass sequences for a given `Backend`, it can be a good idea to start with the passes that solve individual constraints from `required_predicates` (like `FullMappingPass` for `ConnectivityPredicate` or `RebaseX` for `GateSetPredicate`), and find an ordering such that no later pass invalidates the work of an earlier one.
#
# For `MyBackend`, we will need to enforce that our circuits are expressed entirely in terms of `OpType.Rx`, `OpType.Ry`, `OpType.Rz`, and `OpType.ZZMax` gates which we can solve using `RebaseCustom`. Note that we omit `OpType.Measure` since we can only run pure quantum circuits.
#
# The standard docstrings for these and other abstract methods can be seen in the abstract `Backend` [API reference](https://cqcl.github.io/tket/pytket/api/backends.html#pytket.backends.Backend).

from pytket.predicates import Predicate, GateSetPredicate, NoClassicalBitsPredicate
from pytket.passes import (
    BasePass,
    SequencePass,
    DecomposeBoxes,
    SynthesiseTket,
    FullPeepholeOptimise,
    RebaseCustom,
    SquashCustom,
)


@property
def required_predicates(self) -> List[Predicate]:
    """
    The minimum set of predicates that a circuit must satisfy before it can
    be successfully run on this backend.

    :return: Required predicates.
    :rtype: List[Predicate]
    """
    preds = [
        NoClassicalBitsPredicate(),
        GateSetPredicate(
            {
                OpType.Rx,
                OpType.Ry,
                OpType.Rz,
                OpType.ZZMax,
            }
        ),
    ]
    return preds


# Every `Backend` must define a rebasing method, which will normally be called from its default compilation passes (see below), but which may also be called independently. Given the target gate set, it is usually straightforward to define this using the `RebaseCustom` pass, with a couple of helpers defining rebase of an `OpType.CX` and a general `OpType.TK1` gate:

cx_circ = Circuit(2)
cx_circ.Sdg(0)
cx_circ.V(1)
cx_circ.Sdg(1)
cx_circ.Vdg(1)
cx_circ.add_gate(OpType.ZZMax, [0, 1])
cx_circ.Vdg(1)
cx_circ.Sdg(1)
cx_circ.add_phase(0.5)


def sq(a, b, c):
    circ = Circuit(1)
    if c != 0:
        circ.Rz(c, 0)
    if b != 0:
        circ.Rx(b, 0)
    if a != 0:
        circ.Rz(a, 0)
    return circ


rebase = RebaseCustom({OpType.Rx, OpType.Ry, OpType.Rz, OpType.ZZMax}, cx_circ, sq)


def default_compilation_pass(self, optimisation_level: int = 1) -> BasePass:
    """
    A suggested compilation pass that will guarantee the resulting circuit
    will be suitable to run on this backend with as few preconditions as
    possible.

    :param optimisation_level: The level of optimisation to perform during
        compilation. Level 0 just solves the device constraints without
        optimising. Level 1 additionally performs some light optimisations.
        Level 2 adds more intensive optimisations that can increase compilation
        time for large circuits. Defaults to 1.
    :type optimisation_level: int, optional
    :return: Compilation pass guaranteeing required predicates.
    :rtype: BasePass
    """
    assert optimisation_level in range(3)

    squash = SquashCustom({OpType.Rz, OpType.Rx, OpType.Ry}, sq)
    seq = [DecomposeBoxes()]  # Decompose boxes into basic gates
    if optimisation_level == 1:
        seq.append(SynthesiseTket())  # Optional fast optimisation
    elif optimisation_level == 2:
        seq.append(FullPeepholeOptimise())  # Optional heavy optimisation
    seq.append(rebase)  # Map to target gate set
    if optimisation_level != 0:
        seq.append(squash)  # Optionally simplify 1qb gate chains within this gate set
    return SequencePass(seq)


# The `backend_info` property is used for storing various properties of a backend. By default it provides all device information useful for compilation. Typically we would  make it return a class attribute `self._backend_info` that we initialise on construction, but we will define it at point of request here. We use a `FullyConnected` architecture producing an `Architecture` object with couplings between 4 qubits.


from pytket.backends.backendinfo import BackendInfo
from pytket.architecture import FullyConnected


@property
def backend_info(self) -> BackendInfo:
    return BackendInfo(
        "MyBackend",
        "MySimulator",
        "1.0",
        FullyConnected(4),
        {
            OpType.Rx,
            OpType.Ry,
            OpType.Rz,
            OpType.ZZMax,
            OpType.Measure,
        },
        supports_midcircuit_measurement=False,
        misc={"characterisation": None},
    )


# Asynchronous job management is all managed through the `ResultHandle` associated with a particular `Circuit` that has been submitted. We can use it to inspect the status of the job to see if it has completed, or to look up the results if they are available.
#
# For devices, `circuit_status` should query the job to see if it is in a queue, currently being executed, completed successfully, etc. The `CircuitStatus` class is mostly driven by the `StatusEnum` values, but can also contain messages to give more detailed feedback if available. For our simulator, we are not running things asynchronously, so a `Circuit` has either not been run or it will have been completed.
#
# Since a device API will probably define its own data type for job handles, the `ResultHandle` definition is flexible enough to cover many possible data types so you can likely use the underlying job handle as the `ResultHandle`. The `_result_id_type` property specifies what data type a `ResultHandle` for this `Backend` should look like. Since our simulator has no underlying job handle, we can just use a UUID string.

from pytket.backends import ResultHandle, CircuitStatus, StatusEnum, CircuitNotRunError
from pytket.backends.resulthandle import _ResultIdTuple


@property
def _result_id_type(self) -> _ResultIdTuple:
    """Identifier type signature for ResultHandle for this backend.

    :return: Type signature (tuple of hashable types)
    :rtype: _ResultIdTuple
    """
    return (str,)


def circuit_status(self, handle: ResultHandle) -> CircuitStatus:
    """
    Return a CircuitStatus reporting the status of the circuit execution
    corresponding to the ResultHandle
    """
    if handle in self._cache:
        return CircuitStatus(StatusEnum.COMPLETED)
    raise CircuitNotRunError(handle)


# And finally, we have the method that actually submits a job for execution. `process_circuits` should take a collection of (compiled) `Circuit` objects, process them and return a `ResultHandle` for each `Circuit`. If execution is synchronous, then this can simply wait until it is finished, store the result in `_cache` and return. For backends that support asynchronous jobs, you will need to set up an event to format and store the result on completion.
#
# It is recommended to use the `valid_check` parameter to control a call to `Backend._check_all_circuits()`, which will raise an exception if any of the circuits do not satisfy everything in `required_predicates`.
#
# The `_cache` fields stores all of the information about current jobs that have been run. When a job has finished execution, the results are expected to be stored in `_cache[handle]["result"]`, though it can also be used to store other data about the job such as some information about the `Circuit` required to properly format the results. Methods like `Backend.get_result()` and `Backend.empty_cache()` expect to interact with the results of a given job in this way.
#
# The final output of the execution is stored in a `BackendResult` object. This captures enough information about the results to reinterpret it in numerous ways, such as requesting the statevector in a specific qubit ordering or converting a complete shot table to a summary of the counts. If we create a `BackendResult` with quantum data (e.g. a statevector or unitary), we must provide the `Qubit` ids in order from most-significant to least-significant with regards to indexing the state. Similarly, creating one with classical readouts (e.g. a shot table or counts summary), we give the `Bit` ids in the order they appear in a readout (left-to-right).
#
# For a statevector simulation, we should also take into account the global phase stored in the `Circuit` object and any implicit qubit permutations, since these become observable when inspecting the quantum state. We can handle the qubit permutation by changing the order in which we pass the `Qubit` ids into the `BackendResult` object.

from pytket.backends.backendresult import BackendResult
from pytket.utils.results import KwargTypes
from typing import Iterable, Optional
from uuid import uuid4


def process_circuits(
    self,
    circuits: Iterable[Circuit],
    n_shots: Optional[int] = None,
    valid_check: bool = True,
    **kwargs: KwargTypes,
) -> List[ResultHandle]:
    """
    Submit circuits to the backend for running. The results will be stored
    in the backend's result cache to be retrieved by the corresponding
    get_<data> method.

    Use keyword arguments to specify parameters to be used in submitting circuits
    See specific Backend derived class for available parameters, from the following
    list:

    * `seed`: RNG seed for simulators

    :param circuits: Circuits to process on the backend.
    :type circuits: Iterable[Circuit]
    :param n_shots: Number of shots to run per circuit. None is to be used
        for state/unitary simulators. Defaults to None.
    :type n_shots: Optional[int], optional
    :param valid_check: Explicitly check that all circuits satisfy all required
        predicates to run on the backend. Defaults to True
    :type valid_check: bool, optional
    :return: Handles to results for each input circuit, as an interable in
        the same order as the circuits.
    :rtype: List[ResultHandle]
    """

    circuit_list = list(circuits)
    if valid_check:
        self._check_all_circuits(circuit_list)

    handle_list = []
    for circuit in circuit_list:
        handle = ResultHandle(str(uuid4()))
        mycirc = tk_to_mycircuit(circuit)
        state = run_mycircuit(mycirc)
        state *= np.exp(1j * np.pi * circuit.phase)
        implicit_perm = circuit.implicit_qubit_permutation()
        res_qubits = [implicit_perm[qb] for qb in sorted(circuit.qubits, reverse=True)]
        res = BackendResult(q_bits=res_qubits, state=state)
        self._cache[handle] = {"result": res}
        handle_list.append(handle)
    return handle_list


# Let's redefine our `MyBackend` class to use these methods to finish it off.


class MyBackend(Backend):
    """A pytket Backend wrapping around the MySimulator statevector simulator"""

    _supports_state = True
    _persistent_handles = False

    def __init__(self):
        """Create a new instance of the MyBackend class"""
        super().__init__()

    required_predicates = required_predicates
    rebase_pass = rebase
    default_compilation_pass = default_compilation_pass
    _result_id_type = _result_id_type
    circuit_status = circuit_status
    process_circuits = process_circuits


# Our new `Backend` subclass is now complete, so let's test it out. If you are planning on maintaining a backend class, it is recommended to set up some unit tests. The following tests will cover basic operation and integration with `pytket` utilities.

from pytket.circuit import BasisOrder, Unitary1qBox
from pytket.passes import CliffordSimp
from pytket.utils import get_operator_expectation_value
from pytket.utils.operators import QubitPauliOperator
import pytest


def test_bell() -> None:
    c = Circuit(2)
    c.H(0)
    c.CX(0, 1)
    b = MyBackend()
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c)
    assert np.allclose(
        b.get_result(h).get_state(), np.asarray([1, 0, 0, 1]) * 1 / np.sqrt(2)
    )


def test_basisorder() -> None:
    c = Circuit(2)
    c.X(1)
    b = MyBackend()
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c)
    r = b.get_result(h)
    assert np.allclose(r.get_state(), np.asarray([0, 1, 0, 0]))
    assert np.allclose(r.get_state(basis=BasisOrder.dlo), np.asarray([0, 0, 1, 0]))


def test_implicit_perm() -> None:
    c = Circuit(2)
    c.CX(0, 1)
    c.CX(1, 0)
    c.Ry(0.1, 1)
    c1 = c.copy()
    CliffordSimp().apply(c1)
    b = MyBackend()
    c = b.get_compiled_circuit(c, optimisation_level=1)
    c1 = b.get_compiled_circuit(c1, optimisation_level=1)
    assert c.implicit_qubit_permutation() != c1.implicit_qubit_permutation()
    h, h1 = b.process_circuits([c, c1])
    r, r1 = b.get_results([h, h1])
    for bo in [BasisOrder.ilo, BasisOrder.dlo]:
        s = r.get_state(basis=bo)
        s1 = r1.get_state(basis=bo)
        assert np.allclose(s, s1)


def test_compilation_pass() -> None:
    b = MyBackend()
    for opt_level in range(3):
        c = Circuit(2)
        c.CX(0, 1)
        u = np.asarray([[0, 1], [-1j, 0]])
        c.add_gate(Unitary1qBox(u), 1)
        c.CX(0, 1)
        c.add_gate(OpType.CRz, 0.35, [1, 0])
        assert not (b.valid_circuit(c))
        c = b.get_compiled_circuit(c, optimisation_level=opt_level)
        assert b.valid_circuit(c)


def test_invalid_measures() -> None:
    c = Circuit(2)
    c.H(0).CX(0, 1).measure_all()
    b = MyBackend()
    c = b.get_compiled_circuit(c)
    assert not (b.valid_circuit(c))


def test_expectation_value() -> None:
    c = Circuit(2)
    c.H(0)
    c.CX(0, 1)
    op = QubitPauliOperator(
        {
            QubitPauliString({Qubit(0): Pauli.Z, Qubit(1): Pauli.Z}): 1.0,
            QubitPauliString({Qubit(0): Pauli.X, Qubit(1): Pauli.X}): 0.3,
            QubitPauliString({Qubit(0): Pauli.Z, Qubit(1): Pauli.Y}): 0.8j,
            QubitPauliString({Qubit(0): Pauli.Y}): -0.4j,
        }
    )
    b = MyBackend()
    c = b.get_compiled_circuit(c)
    assert get_operator_expectation_value(c, op, b) == pytest.approx(1.3)


# Explicit calls are needed for this notebook. Normally pytest will just find these "test_X" methods when run from the command line:

test_bell()
test_basisorder()
test_implicit_perm()
test_compilation_pass()
test_invalid_measures()
test_expectation_value()

# To show how this compares to a sampling simulator, let's extend our simulator to handle end-of-circuit measurements.

from typing import Set


def sample_mycircuit(
    circ: MyCircuit, qubits: Set[Qubit], n_shots: int, seed: Optional[int] = None
) -> np.ndarray:
    """Run the circuit on the all-|0❭ state and measures a set of qubits

    :param circ: The circuit to simulate
    :type circ: MyCircuit
    :param qubits: The set of qubits to measure
    :type qubits: Set[Qubit]
    :param n_shots: The number of samples to take
    :type n_shots: int
    :param seed: Seed for the random number generator, defaults to no seed
    :type seed: Optional[int], optional
    :return: Table of shots; each row is a shot, columns are qubit readouts in ascending Qubit order
    :rtype: np.ndarray
    """
    state = run_mycircuit(circ)
    cumulative_probs = (state * state.conjugate()).cumsum()
    if seed is not None:
        np.random.seed(seed)
    shots = np.zeros((n_shots, len(circ.qubits)))
    for s in range(n_shots):
        # Pick a random point in the distribution
        point = np.random.uniform(0.0, 1.0)
        # Find the corresponding readout
        index = np.searchsorted(cumulative_probs, point)
        # Convert index to a binary array
        # `bin` maps e.g. index 6 to '0b110'
        # So we ignore the first two symbols and add leading 0s to make it a fixed length
        bitstring = bin(index)[2:].zfill(len(circ.qubits))
        shots[s] = np.asarray([int(b) for b in bitstring])
    filtered = np.zeros((n_shots, len(qubits)))
    target = 0
    for col, q in enumerate(circ.qubits):
        if q in qubits:
            filtered[:, target] = shots[:, col]
            target += 1
    return filtered


# Since `MyCircuit` doesn't have a representation for measurement gates, our converter must return both the `MyCircuit` object and some way of capturing the measurements. Since we will also want to know how they map into our `Bit` ids, the simplest option is just a dictionary from `Qubit` to `Bit`.

from pytket import Bit
from typing import Dict, Tuple


def tk_to_mymeasures(tkc: Circuit) -> Tuple[MyCircuit, Dict[Qubit, Bit]]:
    """Convert a pytket Circuit to a MyCircuit object and a measurement map.
    Supports Rz, Rx, Ry, and ZZMax gates, as well as end-of-circuit measurements.

    :param tkc: The Circuit to convert
    :type tkc: Circuit
    :return: An equivalent MyCircuit object and a map from measured Qubit to the Bit containing the result
    :rtype: Tuple[MyCircuit, Dict[Qubit, Bit]]
    """
    circ = MyCircuit(tkc.qubits)
    measure_map = dict()
    measured_units = (
        set()
    )  # Track measured Qubits/used Bits to identify mid-circuit measurement
    for command in tkc:
        for u in command.args:
            if u in measured_units:
                raise ValueError("Circuit contains a mid-circuit measurement")
        optype = command.op.type
        if optype == OpType.Rx:
            circ.add_gate(
                QubitPauliString(command.args[0], Pauli.X), np.pi * command.op.params[0]
            )
        elif optype == OpType.Ry:
            circ.add_gate(
                QubitPauliString(command.args[0], Pauli.Y), np.pi * command.op.params[0]
            )
        elif optype == OpType.Rz:
            circ.add_gate(
                QubitPauliString(command.args[0], Pauli.Z), np.pi * command.op.params[0]
            )
        elif optype == OpType.ZZMax:
            circ.add_gate(
                QubitPauliString(command.args, [Pauli.Z, Pauli.Z]), np.pi * 0.5
            )
        elif optype == OpType.Measure:
            measure_map[command.args[0]] = command.args[1]
            measured_units.add(command.args[0])
            measured_units.add(command.args[1])
        else:
            raise ValueError("Cannot convert optype to MyCircuit: ", optype)
    return circ, measure_map


# To build a `Backend` subclass for this sampling simulator, we only need to change how we write `required_predicates` and `process_circuits`.

from pytket.predicates import NoMidMeasurePredicate, NoClassicalControlPredicate
from pytket.utils.outcomearray import OutcomeArray


class MySampler(Backend):
    """A pytket Backend wrapping around the MySimulator simulator with readout sampling"""

    _supports_shots = True
    _supports_counts = True
    _persistent_handles = False

    def __init__(self):
        """Create a new instance of the MySampler class"""
        super().__init__()

    rebase_pass = rebase
    default_compilation_pass = default_compilation_pass
    _result_id_type = _result_id_type
    circuit_status = circuit_status

    @property
    def required_predicates(self) -> List[Predicate]:
        """
        The minimum set of predicates that a circuit must satisfy before it can
        be successfully run on this backend.

        :return: Required predicates.
        :rtype: List[Predicate]
        """
        preds = [
            NoClassicalControlPredicate(),
            NoMidMeasurePredicate(),
            GateSetPredicate(
                {
                    OpType.Rx,
                    OpType.Ry,
                    OpType.Rz,
                    OpType.ZZMax,
                    OpType.Measure,
                }
            ),
        ]
        return preds

    def process_circuits(
        self,
        circuits: Iterable[Circuit],
        n_shots: Optional[int] = None,
        valid_check: bool = True,
        **kwargs: KwargTypes,
    ) -> List[ResultHandle]:
        """
        Submit circuits to the backend for running. The results will be stored
        in the backend's result cache to be retrieved by the corresponding
        get_<data> method.

        Use keyword arguments to specify parameters to be used in submitting circuits
        See specific Backend derived class for available parameters, from the following
        list:

        * `seed`: RNG seed for simulators

        :param circuits: Circuits to process on the backend.
        :type circuits: Iterable[Circuit]
        :param n_shots: Number of shots to run per circuit. None is to be used
            for state/unitary simulators. Defaults to None.
        :type n_shots: Optional[int], optional
        :param valid_check: Explicitly check that all circuits satisfy all required
            predicates to run on the backend. Defaults to True
        :type valid_check: bool, optional
        :return: Handles to results for each input circuit, as an interable in
            the same order as the circuits.
        :rtype: List[ResultHandle]
        """

        circuit_list = list(circuits)
        if valid_check:
            self._check_all_circuits(circuit_list)

        handle_list = []
        for circuit in circuit_list:
            handle = ResultHandle(str(uuid4()))
            mycirc, measure_map = tk_to_mymeasures(circuit)
            qubit_list, bit_list = zip(*measure_map.items())
            qubit_shots = sample_mycircuit(
                mycirc, set(qubit_list), n_shots, kwargs.get("seed")
            )
            # Pad shot table with 0 columns for unused bits
            all_shots = np.zeros((n_shots, len(circuit.bits)), dtype=int)
            all_shots[:, : len(qubit_list)] = qubit_shots
            res_bits = [measure_map[q] for q in sorted(qubit_list, reverse=True)]
            for b in circuit.bits:
                if b not in bit_list:
                    res_bits.append(b)
            res = BackendResult(
                c_bits=res_bits, shots=OutcomeArray.from_readouts(all_shots)
            )
            self._cache[handle] = {"result": res}
            handle_list.append(handle)
        return handle_list


# Likewise, we run some basic tests to make sure it works.


def test_sampler_bell() -> None:
    c = Circuit(2, 2)
    c.H(0)
    c.CX(0, 1)
    c.measure_all()
    b = MySampler()
    c = b.get_compiled_circuit(c)
    res = b.run_circuit(c, n_shots=10, seed=3)
    assert res.get_shots().shape == (10, 2)
    assert res.get_counts() == {(0, 0): 5, (1, 1): 5}


def test_sampler_basisorder() -> None:
    c = Circuit(2, 2)
    c.X(1)
    c.measure_all()
    b = MySampler()
    c = b.get_compiled_circuit(c)
    res = b.run_circuit(c, n_shots=10, seed=0)
    assert res.get_counts() == {(0, 1): 10}
    assert res.get_counts(basis=BasisOrder.dlo) == {(1, 0): 10}


def test_sampler_compilation_pass() -> None:
    b = MySampler()
    for opt_level in range(3):
        c = Circuit(2)
        c.CX(0, 1)
        u = np.asarray([[0, 1], [-1j, 0]])
        c.add_gate(Unitary1qBox(u), 1)
        c.CX(0, 1)
        c.add_gate(OpType.CRz, 0.35, [1, 0])
        c.measure_all()
        assert not (b.valid_circuit(c))
        c = b.get_compiled_circuit(c, optimisation_level=opt_level)
        assert b.valid_circuit(c)


def test_sampler_expectation_value() -> None:
    c = Circuit(2)
    c.H(0)
    c.CX(0, 1)
    op = QubitPauliOperator(
        {
            QubitPauliString({Qubit(0): Pauli.Z, Qubit(1): Pauli.Z}): 1.0,
            QubitPauliString({Qubit(0): Pauli.X, Qubit(1): Pauli.X}): 0.3,
            QubitPauliString({Qubit(0): Pauli.Z, Qubit(1): Pauli.Y}): 0.8j,
            QubitPauliString({Qubit(0): Pauli.Y}): -0.4j,
        }
    )
    b = MySampler()
    c = b.get_compiled_circuit(c)
    expectation = get_operator_expectation_value(c, op, b, n_shots=2000, seed=0)
    assert (np.real(expectation), np.imag(expectation)) == pytest.approx(
        (1.3, 0.0), abs=0.1
    )


test_sampler_bell()
test_sampler_basisorder()
test_sampler_compilation_pass()
test_sampler_expectation_value()

# Exercises:
# - Add some extra gate definitions to the simulator and expand the accepted gate set of the backends. Start with some that are easily represented as exponentiated Pauli tensors like `OpType.YYPhase`. For a challenge, try adding `OpType.CCX` efficiently (it is possible to encode it using seven Pauli rotations).
# - Restrict the simulator to a limited qubit connectivity. Express this in the backends by modifying the `Architecture` property of the `BackendInfo` attribute object and adding to the `required_predicates`. Adjust the `default_compilation_pass` to solve for the connectivity.
# - The file `creating_backends_exercise.py` extends the simulators above to allow for mid-circuit measurement and conditional gates using a binary decision tree. Implement an appropriate converter and `Backend` class for this simulator.
