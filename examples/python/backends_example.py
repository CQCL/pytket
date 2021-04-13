# # Backends: tket example

# This example shows how to use `pytket` to execute quantum circuits on both simulators and real devices, and how to interpret the results. As tket is designed to be platform-agnostic, we have unified the interfaces of different providers as much as possible into the `Backend` class for maximum portability of code. The following is a selection of currently supported backends:
# * ProjectQ simulator
# * Aer simulators (statevector, QASM, and unitary)
# * IBMQ devices
# * Rigetti QCS devices
# * Rigetti QVM (for device simulation or statevector)
# * AQT devices
# * Honeywell devices
# * Q# simulators

# In this notebook we will focus on the Aer, IBMQ and ProjectQ backends.
#
# To get started, we must install the core pytket package and the subpackages required to interface with the desired providers. We will also need the `QubitOperator` class from `openfermion` to construct operators for a later example. To get everything run the following in shell:
#
# `pip install pytket pytket-qiskit pytket-projectq openfermion`
#
# First, import the backends that we will be demonstrating.

from pytket.extensions.qiskit import (
    AerStateBackend,
    AerBackend,
    AerUnitaryBackend,
    IBMQBackend,
    IBMQEmulatorBackend,
)
from pytket.extensions.projectq import ProjectQBackend

# We are also going to be making a circuit to run on these backends, so import the `Circuit` class.

from pytket import Circuit

# Below we generate a circuit which will produce a Bell state, assuming the qubits are all initialised in the |0> state:

circ = Circuit(2)
circ.H(0)
circ.CX(0, 1)

# As a sanity check, we will use the `AerStateBackend` to verify that `circ` does actually produce a Bell state.
#
# To submit a circuit for excution on a backend we can use `process_circuit` with appropriate arguments. If we have multiple circuits to excecute, we can use `process_circuits` (note the plural), which will attempt to batch up the circuits if possible. Both methods return a `ResultHandle` object per submitted `Circuit` which you can use with result retrieval methods to get the result type you want (as long as that result type is supported by the backend).
#
# Calling `get_state` will return a `numpy` array corresponding to the statevector.
#
# This style of usage is used consistently in the `pytket` backends.

aer_state_b = AerStateBackend()
state_handle = aer_state_b.process_circuit(circ)
statevector = aer_state_b.get_result(state_handle).get_state()
print(statevector)

# As we can see, the output state vector $\lvert \psi_{\mathrm{circ}}\rangle$ is $(\lvert00\rangle + \lvert11\rangle)/\sqrt2$.
#
# This is a symmetric state. For non-symmetric states, we default to an ILO-BE format (increasing lexicographic order of (qu)bit ids, big-endian), but an alternative convention can be specified when retrieving results from backends. See the docs for the `BasisOrder` enum for more information.

# A lesser-used simulator available through Qiskit Aer is their unitary simulator. This will be somewhat more expensive to run, but returns the full unitary matrix for the provided circuit. This is useful in the design of small subcircuits that will be used multiple times within other larger circuits - statevector simulators will only test that they act correctly on the $\lvert 0 \rangle^{\otimes n}$ state, which is not enough to guarantee the circuit's correctness.
#
# The `AerUnitaryBackend` provides a convenient access point for this simulator for use with `pytket` circuits. This is a special case for a backend, as it provides a non standard `get_unitary` interface. The other non-standard backend is the `QsharpEstimatorBackend` provided in `pytket_qsharp` which exposes a `get_resources` method for resource estimation.

aer_unitary_b = AerUnitaryBackend()
print(aer_unitary_b.get_unitary(circ))

# Now suppose we want to measure this Bell state to get some actual results out, so let's append some `Measure` gates to the circuit. The `Circuit` class has the `measure_all` utility function which appends `Measure` gates on every qubit. All of these results will be written to the default classical register ('c'). This function will automatically add the classical bits to the circuit if they are not already there.

circ.measure_all()

# We can get some measured shots out from the `AerBackend`, which is an interface to the Qiskit Aer QASM simulator. Suppose we would like to get 10 shots out (10 repeats of the circuit and measurement). We can seed the simulator's random-number generator in order to make the results reproducible, using an optional keyword argument to `process_circuit`.

aer_b = AerBackend()
shots_handle = aer_b.process_circuit(circ, n_shots=10, seed=1)

shots = aer_b.get_result(shots_handle).get_shots()
print(shots)

# Shot tables are just numpy arrays where each row gives the final readout for each circuit run, and each column represents one of the classical bits in the circuit (ordered lexicographically, so the row `[1 0]` means bit 0 had value 1 and bit 1 had value 0).
#
# In this case there is a 40/60 split between $00$ and $11$ results. If we change the seed, or remove it, we will get varying results according to the pseudo-random number generation internal to Qiskit's QASM simulator.
#
# What happens if we simulate some noise in our imagined device, using the Qiskit Aer noise model?

# To investigate this, we will require an import from Qiskit. For more information about noise modelling using Qiskit Aer, see the [Qiskit device noise](https://qiskit.org/documentation/apidoc/aer_noise.html) documentation.

from qiskit.providers.aer.noise import NoiseModel

my_noise_model = NoiseModel()
readout_error = 0.2
for q in range(2):
    my_noise_model.add_readout_error(
        [[1 - readout_error, readout_error], [readout_error, 1 - readout_error]], [q]
    )

# This simple noise model gives a 20% chance that, upon measurement, a qubit that would otherwise have been measured as $0$ would instead be measured as $1$, and vice versa. Let's see what our shot table looks like with this model:

noisy_aer_b = AerBackend(my_noise_model)
noisy_shots_handle = noisy_aer_b.process_circuit(
    circ, n_shots=10, seed=1, valid_check=False
)
noisy_shots = noisy_aer_b.get_result(noisy_shots_handle).get_shots()
print(noisy_shots)

# We now have some spurious $01$ and $10$ measurements, which could never happen when measuring a Bell state on a noiseless device.
#
# The `AerBackend` class can accept any Qiskit noise model.

# Suppose that we don't need the full shot table, but just want a summary of the results. The most common summary is the counts map, mapping the readout state to the number of times it was observed. We can retrieve this directly using `backend.get_counts` for those backends that support it, or use a utility function.

from pytket.utils import counts_from_shot_table

print(counts_from_shot_table(noisy_shots))

# All backends expose a generic `get_result` method which takes a `ResultHandle` and returns the respective result in the form of a `BackendResult` object. This object may hold measured results in the form of shots or counts, or an exact statevector from simulation. Measured results are stored as `OutcomeArray` objects, which compresses measured bit values into 8-bit integers. We can extract the bitwise values using `to_readouts`.
#
# Instead of an assumed ILO or DLO convention, we can use this object to request only the `Bit` measurements we want, in the order we want. Let's try reversing the bits of the noisy results.

backend_result = noisy_aer_b.get_result(noisy_shots_handle)
bits = circ.bits

outcomes = backend_result.get_shots([bits[1], bits[0]])
print(outcomes)

# `BackendResult` objects can be natively serialized to and deserialized from a dictionary. This dictionary can be immediately dumped to `json` for storing results.

from pytket.backends.backendresult import BackendResult

result_dict = backend_result.to_dict()
print(result_dict)
print(BackendResult.from_dict(result_dict).get_counts())

# The last simulator we will demonstrate is the `ProjectQBackend`. ProjectQ offers fast simulation of quantum circuits with built-in support for fast expectation values from operators. The `ProjectQBackend` exposes this functionality to take in OpenFermion `QubitOperator` instances. These are convertible to and from `QubitPauliOperator` instances in Pytket.
#
# Note: ProjectQ can also produce statevectors in the style of `AerStateBackend`, and similarly Aer backends can calculate expectation values directly, consult the relevant documentation to see more.
#
# Let's create a `QubitOperator` object and a new circuit:

from openfermion import QubitOperator

hamiltonian = 0.5 * QubitOperator("X0 X2") + 0.3 * QubitOperator("Z0")

circ2 = Circuit(3)
circ2.Y(0)
circ2.H(1)
circ2.Rx(0.3, 2)

# Now we can create a `ProjectQBackend` instance and feed it our circuit and `QubitOperator`:

from pytket.utils.operators import QubitPauliOperator

projectq_b = ProjectQBackend()
expectation = projectq_b.get_operator_expectation_value(
    circ2, QubitPauliOperator.from_OpenFermion(hamiltonian)
)
print(expectation)

# The last leg of this tour includes running a pytket circuit on an actual quantum computer. To do this, you will need an IBM quantum experience account and have your credentials stored on your computer. See https://quantum-computing.ibm.com to make an account and view available devices and their specs.
#
# Physical devices have much stronger constraints on the form of admissible circuits than simulators. They tend to support a minimal gate set, have restricted connectivity between qubits for two-qubit gates, and can have limited support for classical control flow or conditional gates. This is where we can invoke the tket compiler passes to transform our desired circuit into one that is suitable for the backend.
#
# To check our code works correctly, we can use the `IBMQEmulatorBackend` to run our code exactly as if it were going to run on a real device, but just execute on a simulator (with a basic noise model adapted from the reported device properties).


# Let's create an `IBMQEmulatorBackend` for the `ibmq_santiago` device and check if our circuit is valid to be run.

ibmq_b_emu = IBMQEmulatorBackend("ibmq_santiago")
ibmq_b_emu.valid_circuit(circ)

# It looks like we need to compile this circuit to be compatible with the device. To simplify this procedure, we provide minimal compilation passes designed for each backend (the `default_compilation_pass()` method) which will guarantee compatibility with the device. These may still fail if the input circuit has too many qubits or unsupported usage of conditional gates. The default passes can have their degree of optimisation by changing an integer parameter (optimisation levels 0, 1, 2), and they can be easily composed with any of tket's other optimisation passes for better performance.
#
# For convenience, we also wrap up this pass into the `compile_circuit` method if you just want to compile a single circuit.

ibmq_b_emu.compile_circuit(circ)


# Let's create a backend for running on the actual device and check our compiled circuit is valid for this backend too.

ibmq_b = IBMQBackend("ibmq_santiago")
ibmq_b.valid_circuit(circ)

# We are now good to run this circuit on the device. After submitting, we can use the handle to check on the status of the job, so that we know when results are ready to be retrieved. The `circuit_status` method works for all backends, and returns a `CircuitStatus` object. If we just run `get_result` straight away, the backend will wait for results to complete, blocking any other code from running.
#
# In this notebook we will use the emulated backend `ibmq_b_emu` to illustrate, but the workflow is the same as for the real backend `ibmq_b` (except that the latter will typically take much longer because of the size of the queue).

quantum_handle = ibmq_b_emu.process_circuit(circ, n_shots=10)

print(ibmq_b_emu.circuit_status(quantum_handle))

quantum_shots = ibmq_b_emu.get_result(quantum_handle).get_shots()
print(quantum_shots)

# These are from an actual device, so it's impossible to perfectly predict what the results will be. However, because of the problem of noise, it would be unsurprising to find a few $01$ or $10$ results in the table. The circuit is very short, so it should be fairly close to the ideal result.
#
# The devices available through the IBM Q Experience serve jobs one at a time from their respective queues, so a large amount of experiment time can be taken up by waiting for your jobs to reach the front of the queue. `pytket` allows circuits to be submitted to any backend in a single batch using the `process_circuits` method. For the `IBMQBackend`, this will collate the circuits into as few jobs as possible which will all be sent off into the queue for the device. The method returns a `ResultHandle` per submitted circuit, in the order of submission.

circuits = []
for i in range(5):
    c = Circuit(2)
    c.Rx(0.2 * i, 0).CX(0, 1)
    c.measure_all()
    ibmq_b_emu.compile_circuit(c)
    circuits.append(c)
handles = ibmq_b_emu.process_circuits(circuits, n_shots=100)
print(handles)

# We can now retrieve the results and process them. As we measured each circuit in the $Z$-basis, we can obtain the expectation value for the $ZZ$ operator immediately from these measurement results. We can calculate this using the `expectation_value_from_shots` utility method in `pytket`.

from pytket.utils import expectation_from_shots

for handle in handles:
    shots = ibmq_b_emu.get_result(handle).get_shots()
    exp_val = expectation_from_shots(shots)
    print(exp_val)

# A `ResultHandle` can be easily stored in its string representaton and later reconstructed using the `from_str` method. For example, we could do something like this:

from pytket.backends import ResultHandle

c = Circuit(2).Rx(0.5, 0).CX(0, 1).measure_all()
ibmq_b_emu.compile_circuit(c)
handle = ibmq_b_emu.process_circuit(c, n_shots=10)
handlestring = str(handle)
print(handlestring)
# ... later ...
oldhandle = ResultHandle.from_str(handlestring)
print(ibmq_b_emu.get_result(oldhandle).get_shots())

# For backends which support persistent handles (currently `IBMQBackend`, `HoneywellBackend`, `BraketBackend` and `AQTBackend`) you can even stop your python session and use your result handles in a separate script to retrive results when they are ready, by storing the handle strings. For experiments with long queue times, this enables separate job submission and retrieval. Use `Backend.persistent_handles` to check whether a backend supports this feature.
#
# All backends will also cache all results obtained in the current python session, so you can use the `ResultHandle` to retrieve the results many times if you need to reuse the results. Over a long experiment, this can consume a large amount of RAM, so we recommend removing results from the cache when you are done with them. A simple way to achieve this is by calling `Backend.empty_cache` (e.g. at the end of each loop of a variational algorithm), or removing individual results with `Backend.pop_result`.

# The backends in `pytket` are designed to be as similar to one another as possible. The example above using physical devices can be run entirely on a simulator by swapping out the `IBMQBackend` constructor for any other backend supporting shot outputs (e.g. `AerBackend`, `ProjectQBackend`, `ForestBackend`), or passing it the name of a different device. Furthermore, using pytket it is simple to convert between handling shot tables, counts maps and statevectors.
#
# For more information on backends and other `pytket` features, read our [documentation](https://cqcl.github.io/pytket) or see the other examples on our [GitHub repo](https://github.com/CQCL/pytket).
