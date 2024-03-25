*******************
Running on Backends
*******************

.. Co-processor model of QC; circuits are the units of tasks

The interaction model for quantum computing in the near future is set to follow the co-processor model: there is a main program running on the classical host computer which routinely sends off jobs to a specialist device that can handle that class of computation efficiently, similar to interacting with GPUs and cloud HPC resources. We have already seen how to use ``pytket`` to describe a job to be performed with the :py:class:`~pytket.circuit.Circuit` class; the next step is to look at how we interact with the co-processor to run it.

.. Backends manage sending the circuits to be processed (by simulator or device) and retrieving results; general workflow of compile, process, retrieve


A :py:class:`~pytket.backends.Backend` represents a connection to some co-processor instance, which can be either quantum hardware or a simulator. It presents a uniform interface for submitting :py:class:`~pytket.circuit.Circuit` s to be processed and retrieving the results, allowing the general workflow of "generate, compile, process, retrieve, interpret" to be performed with little dependence on the specific co-processor used. This is to promote the development of platform-independent software, helping the code that you write to be more future-proof and encouraging exploration of the ever-changing landscape of quantum hardware solutions.

With the wide variety of :py:class:`~pytket.backends.Backend` s available, they naturally have very different capabilities and limitations. The class is designed to open up this information so that it is easy to examine at runtime and make hardware-dependent choices as needed for maximum performance, whilst providing a basic abstract model that is easy for proof-of-concept testing.

No :py:class:`~pytket.backends.Backend` s are currently provided with the core `pytket <https://tket.quantinuum.com/api-docs/>`_ package, but most extension modules will add simulators or devices from the given provider, such as the :py:class:`~pytket.extensions.qiskit.AerBackend` and :py:class:`~pytket.extensions.qiskit.IBMQBackend` with `pytket-qiskit <https://tket.quantinuum.com/extensions/pytket-qiskit/>`_ or the :py:class:`~pytket.extensions.quantinuum.QuantinuumBackend` with `pytket-quantinuum <https://tket.quantinuum.com/extensions/pytket-quantinuum/>`_.

Backend Requirements
--------------------

.. Not every circuit can be run immediately on a device or simulator; restrictions put in place for ease of implementation or limitations of engineering or noise
.. Devices and simulators are designed to only support a small gate set, but since they are universal, it is enough to compile to them

Every device and simulator will have some restrictions to allow for a simpler implementation or because of the limits of engineering or noise within a device. For example, devices and simulators are typically designed to only support a small (but universal) gate set, so a :py:class:`~pytket.circuit.Circuit` containing other gate types could not be run immediately. However, as long as the fragment supported is universal, it is enough to be able to compile down to a semantically-equivalent :py:class:`~pytket.circuit.Circuit` which satisfies the requirements, for example, by translating each unknown gate into sequences of known gates.

.. Other common restrictions are on the number and connectivity of qubits - a multi-qubit gate may only be possible to perform on adjacent qubits on the architecture

Other common restrictions presented by QPUs include the number of available qubits and their connectivity (multi-qubit gates may only be performed between adjacent qubits on the architecture). Measurements may also be noisy or take a long time on some QPUs, leading to the destruction or decoherence of any remaining quantum state, so they are artificially restricted to only happen in a single layer at the end of execution and mid-circuit measurements are rejected. More extremely, some classes of classical simulators will reject measurements entirely as they are designed to simulate pure quantum circuits (for example, when looking to yield a statevector or unitary deterministically).

.. Each restriction on the circuits is captured by a `Predicate`
.. Querying the requirements of a given backend

Each :py:class:`~pytket.backends.Backend` object is aware of the restrictions of the underlying device or simulator, encoding them as a collection of :py:class:`~pytket.predictate.Predicate` s. Each :py:class:`~pytket.predictate.Predicate` is essentially a Boolean property of a :py:class:`~pytket.circuit.Circuit` which must return ``True`` for the :py:class:`~pytket.circuit.Circuit` to successfully run. The set of :py:class:`~pytket.predicates.Predicate` s required by a :py:class:`~pytket.backends.Backend` can be queried with :py:attr:`~pytket.backends.Backend.required_predicates`.

.. jupyter-input::

    from pytket.extensions.qiskit import IBMQBackend, AerStateBackend

    dev_b = IBMQBackend("ibmq_quito")
    sim_b = AerStateBackend()
    print(dev_b.required_predicates)
    print(sim_b.required_predicates)

.. jupyter-output::

    [NoClassicalControlPredicate, NoFastFeedforwardPredicate, NoMidMeasurePredicate, NoSymbolsPredicate, GateSetPredicate:{ U1 noop U2 CX Barrier Measure U3 }, DirectednessPredicate:{ Nodes: 5, Edges: 8 }]
    [NoClassicalControlPredicate, NoFastFeedforwardPredicate, GateSetPredicate:{ CU1 CZ CX Unitary2qBox Sdg U1 Unitary1qBox SWAP S U2 CCX Y U3 Z X T noop Tdg Reset H }]

.. Can check if a circuit satisfies all requirements with `valid_circuit`
.. `get_compiled_circuit` modifies a circuit to try to satisfy all backend requirements if possible (restrictions on measurements or conditional gate support may not be fixed by compilation)

Knowing the requirements of each :py:class:`~pytket.backends.Backend` is handy in case it has consequences for how you design a :py:class:`~pytket.circuit.Circuit`, but can generally be abstracted away. Calling :py:meth:`~pytket.backends.Backend.valid_circuit()` can check whether or not a :py:class:`~pytket.circuit.Circuit` satisfies every requirement to run on the :py:class:`~pytket.backends.Backend`, and if it is not immediately valid then :py:meth:`~pytket.backends.Backend.get_compiled_circuit` will try to solve all of the remaining constraints when possible (note that restrictions on measurements or conditional gate support may not be fixed by compilation), and return a new :py:class:`~pytket.circuit.Circuit`.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.extensions.qiskit import AerBackend

    circ = Circuit(2, 2)
    circ.Rx(0.3, 0).Ry(0.5, 1).CRz(-0.6, 1, 0).measure_all()

    backend = AerBackend()
    if not backend.valid_circuit(circ):
        compiled_circ = backend.get_compiled_circuit(circ)
        assert backend.valid_circuit(compiled_circ)

    print(compiled_circ.get_commands())

Now that we can prepare our :py:class:`~pytket.circuit.Circuit` s to be suitable for a given :py:class:`~pytket.backends.Backend`, we can send them off to be run and examine the results. This is always done by calling :py:meth:`~pytket.backends.Backend.process_circuit()` which sends a :py:class:`~pytket.circuit.Circuit` for execution and returns a :py:class:`~pytket.backends.resulthandle.ResultHandle` as an identifier for the job which can later be used to retrieve the actual results once the job has finished.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.extensions.qiskit import AerStateBackend

    circ = Circuit(2, 2)
    circ.Rx(0.3, 0).Ry(0.5, 1).CRz(-0.6, 1, 0)
    backend = AerStateBackend()
    compiled_circ = backend.get_compiled_circuit(circ)
    handle = backend.process_circuit(compiled_circ)

The exact arguments to :py:meth:`~pytket.backends.Backend.process_circuit` and the means of retrieving results back are dependent on the type of data the :py:class:`~pytket.backends.Backend` can produce and whether it samples measurements or calculates the internal state of the quantum system.

Shots and Sampling
------------------

.. On real devices, cannot directly inspect the statevector of quantum system, so only classical output is the results of measurements
.. Measurements are not deterministic, so each run samples from some distribution; refer to each full run of the circuit from the initial state as a "shot"

Running a :py:class:`~pytket.circuit.Circuit` on a quantum computer invovles applying the instructions to some quantum system to modify its state. Whilst we know that this state will form a vector (or linear map) in some Hilbert space, we cannot directly inspect it and obtain a complex vector/matrix to return to the classical host process. The best we can achieve is performing measurements to collapse the state and obtain a bit of information in the process. Since the measurements are not deterministic, each run of the :py:class:`~pytket.circuit.Circuit` samples from some distribution. By obtaining many *shots* (the classical readout from each full run of the :py:class:`~pytket.circuit.Circuit` from the initial state), we can start to predict what the underlying measurement distrubution looks like.

.. Retrieve table of results using `get_shots`; rows are shots (in order of execution), columns are bits (in ILO)

The interaction with a QPU (or a simulator that tries to imitate a device by sampling from the underlying complex statevector) is focused around requesting shots for a given :py:class:`~pytket.circuit.Circuit`. The number of shots required is passed to :py:meth:`~pytket.backends.Backend.process_circuit()`. The result is retrieved using :py:meth:`~pytket.backends.Backend.get_result()`; and the shots are then given as a table from :py:meth:`~pytket.backends.BackendResult.get_shots()`: each row of the table describes a shot in the order of execution, and the columns are the classical bits from the :py:class:`~pytket.circuit.Circuit`.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.extensions.qiskit import AerBackend

    circ = Circuit(2, 2)
    circ.H(0).X(1).measure_all()
    backend = AerBackend()
    compiled_circ = backend.get_compiled_circuit(circ)

    handle = backend.process_circuit(compiled_circ, n_shots=20)
    shots = backend.get_result(handle).get_shots()
    print(shots)

.. Often interested in probabilities of each measurement outcome, so need many shots for high precision
.. Even if we expect a single peak in distribution, will want many shots to account for noise

For most applications, we are interested in the probability of each measurement outcome, so we need many shots for each experiment for high precision (it is quite typical to ask for several thousand or more). Even if we expect a single sharp peak in the distribution, as is the case from many of the popular textbook quantum algorithms (Deutsch-Jozsa, Bernstein-Vazirani, Shor, etc.), we will generally want to take many shots to help account for noise.

.. If we don't need order of results, can get summary of counts using `get_counts`

If we don't care about the temporal order of the shots, we can instead retrieve a compact summary of the frequencies of observed results. The dictionary returned by :py:meth:`~pytket.backends.BackendResult.get_counts` maps tuples of bits to the number of shots that gave that result (keys only exist in the dictionary if this is non-zero). If probabilities are preferred to frequencies, we can apply the utility method :py:meth:`~pytket.backends.BackendResult.probs_from_counts()`.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.extensions.qiskit import AerBackend
    from pytket.utils import probs_from_counts

    circ = Circuit(2, 2)
    circ.H(0).X(1).measure_all()
    backend = AerBackend()
    compiled_circ = backend.get_compiled_circuit(circ)

    handle = backend.process_circuit(compiled_circ, n_shots=2000)
    counts = backend.get_result(handle).get_counts()
    print(counts)

    print(probs_from_counts(counts))

.. note:: :py:class:`~pytket.backends.Backend.process_circuit` returns a handle to the computation to perform the quantum computation asynchronously. Non-blocking operations are essential when running circuits on remote devices, as submission and queuing times can be long. The handle may then be used to retrieve the results with :py:class:`~pytket.backends.Backend.get_result`. If asynchronous computation is not needed, for example when running on a local simulator, pytket provides the shortcut :py:meth:`pytket.backends.Backend.run_circuit` that will immediately execute the circuit and return a :py:class:`~pytket.backends.backendresult.BackendResult`.

Statevector and Unitary Simulation with TKET Backends
-----------------------------------------------------

.. Any form of sampling introduces non-deterministic error, so for better accuracy we will want the exact state of the physical system; some simulators will provide direct access to this
.. `get_state` gives full representation of that system's state in the 2^n-dimensional complex Hilbert space

Any form of sampling from a distribution will introduce sampling error and (unless it is a seeded simulator) non-deterministic results, whereas we could get much better accuracy and repeatability if we have the exact state of the underlying physical quantum system. Some simulators will provide direct access to this. The :py:meth:`~pytket.backends.BackendResult.get_state` method will give the full representation of the physical state as a vector in the :math:`2^n`-dimensional Hilbert space, whenever the underlying simulator provides this.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.extensions.qiskit import AerStateBackend

    circ = Circuit(3)
    circ.H(0).CX(0, 1).S(1).X(2)
    backend = AerStateBackend()
    compiled_circ = backend.get_compiled_circuit(circ)

    state = backend.run_circuit(compiled_circ).get_state()
    print(state.round(5))

.. note:: We have rounded the results here because simulators typically introduce a small amount of floating-point error, so killing near-zero entries gives a much more readable representation.

.. `get_unitary` treats circuit with open inputs and gives map on 2^n-dimensional complex Hilbert space

The majority of :py:class:`~pytket.backends.Backend` s will run the :py:class:`~pytket.circuit.Circuit` on the initial state :math:`|0\rangle^{\otimes n}`. However, because we can form the composition of :py:class:`~pytket.circuit.Circuit` s, we want to be able to test them with open inputs. When the :py:class:`~pytket.circuit.Circuit` is purely quantum, we can represent its effect as an open circuit by a unitary matrix acting on the :math:`2^n`-dimensional Hilbert space. The :py:class:`~pytket.extensions.qiskit.AerUnitaryBackend` from ``pytket-qiskit`` is designed exactly for this.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.extensions.qiskit import AerUnitaryBackend

    circ = Circuit(2)
    circ.H(0).CX(0, 1)
    backend = AerUnitaryBackend()
    compiled_circ = backend.get_compiled_circuit(circ)

    unitary = backend.run_circuit(compiled_circ).get_unitary()
    print(unitary.round(5))

.. Useful for obtaining high-precision results as well as verifying correctness of circuits
.. Utilities for mapping between shots/counts/probabilities/state and comparing statevectors/unitaries up to global phase

Whilst the drive for quantum hardware is driven by the limited scalability of simulators, using statevector and unitary simulators will see long-term practical use to obtain high-precision results as well as for verifying the correctness of circuit designs. For the latter, we can assert that they match some expected reference state, but simply comparing the vectors/matrices may be too strict a test given that they could differ by a global phase but still be operationally equivalent. The utility methods :py:meth:`~pytket.utils.compare_statevectors()` and :py:meth:`~pytket.utils.compare_unitaries()` will compare two vectors/matrices for approximate equivalence accounting for global phase.

.. jupyter-execute::

    from pytket.utils.results import compare_statevectors
    import numpy as np

    ref_state = np.asarray([1, 0, 1, 0]) / np.sqrt(2.)      # |+0>
    gph_state = np.asarray([1, 0, 1, 0]) * 1j / np.sqrt(2.) # i|+0>
    prm_state = np.asarray([1, 1, 0, 0]) / np.sqrt(2.)      # |0+>

    print(compare_statevectors(ref_state, gph_state))   # Differ by global phase
    print(compare_statevectors(ref_state, prm_state))   # Differ by qubit permutation

.. Warning that interactions with classical data (conditional gates and measurements) or deliberately collapsing the state (Collapse and Reset) do not yield a deterministic result in this Hilbert space, so will be rejected

Be warned that simulating any :py:class:`~pytket.circuit.Circuit` that interacts with classical data (e.g. conditional gates and measurements) or deliberately collapses the quantum state (e.g. ``OpType.Collapse`` and ``OpType.Reset``) would not yield a deterministic result in the system's Hilbert space, so these will be rejected by the :py:class:`~pytket.backends.Backend`.

Interpreting Results
--------------------

Once we have obtained these results, we still have the matter of understanding what they mean. This corresponds to asking "which (qu)bit is which in this data structure?"

.. Ordering of basis elements/readouts (ILO vs DLO; requesting custom order)

By default, the bits in readouts (shots and counts) are ordered in Increasing Lexicographical Order (ILO) with respect to their :py:class:`~pytket.unit_id.UnitID` s. That is, the register ``c`` will be listed completely before any bits in register ``d``, and within each register the indices are given in increasing order. Many quantum software platforms including Qiskit and pyQuil will natively use the reverse order (Decreasing Lexicographical Order - DLO), so users familiar with them may wish to request that the order is changed when retrieving results.

.. jupyter-execute::

    from pytket.circuit import Circuit, BasisOrder
    from pytket.extensions.qiskit import AerBackend

    circ = Circuit(2, 2)
    circ.X(1).measure_all()     # write 0 to c[0] and 1 to c[1]
    backend = AerBackend()
    compiled_circ = backend.get_compiled_circuit(circ)
    handle = backend.process_circuit(compiled_circ, n_shots=10)
    result = backend.get_result(handle)

    print(result.get_counts())   # ILO gives (c[0], c[1]) == (0, 1)
    print(result.get_counts(basis=BasisOrder.dlo))  # DLO gives (c[1], c[0]) == (1, 0)

The choice of ILO or DLO defines the ordering of a bit sequence, but this can still be interpreted into the index of a statevector in two ways: by mapping the bits to a big-endian (BE) or little-endian (LE) integer. Every statevector and unitary in ``pytket`` uses a BE encoding (if LE is preferred, note that the ILO-LE interpretation gives the same result as DLO-BE for statevectors and unitaries, so just change the ``basis`` argument accordingly). The ILO-BE convention gives unitaries of individual gates as they typically appear in common textbooks [Niel2001]_.

.. jupyter-execute::

    from pytket.circuit import Circuit, BasisOrder
    from pytket.extensions.qiskit import AerUnitaryBackend

    circ = Circuit(2)
    circ.CX(0, 1)
    backend = AerUnitaryBackend()
    compiled_circ = backend.get_compiled_circuit(circ)
    handle = backend.process_circuit(compiled_circ)
    result = backend.get_result(handle)

    print(result.get_unitary())
    print(result.get_unitary(basis=BasisOrder.dlo))

Suppose that we only care about a subset of the measurements used in a :py:class:`~pytket.circuit.Circuit`. A shot table is a ``numpy.ndarray``, so it can be filtered by column selections. To identify which columns need to be retained/removed, we are able to predict their column indices from the :py:class:`~pytket.circuit.Circuit` object. :py:attr:`pytket.Circuit.bit_readout` maps :py:class:`~pytket.unit_id.Bit` s to their column index (assuming the ILO convention).

.. jupyter-execute::

    from pytket import Circuit, Bit
    from pytket.extensions.qiskit import AerBackend
    from pytket.utils import expectation_from_shots

    circ = Circuit(3, 3)
    circ.Rx(0.3, 0).CX(0, 1).CZ(1, 2)   # Generate the state we want to consider

    circ.H(1)   # Measure ZXY operator qubit-wise
    circ.Rx(0.5, 2)
    circ.measure_all()

    backend = AerBackend()
    compiled_circ = backend.get_compiled_circuit(circ)
    handle = backend.process_circuit(compiled_circ, 2000)
    shots = backend.get_result(handle).get_shots()

    # To extract the expectation value for ZIY, we only want to consider bits c[0] and c[2]
    bitmap = compiled_circ.bit_readout
    shots = shots[:, [bitmap[Bit(0)], bitmap[Bit(2)]]]
    print(expectation_from_shots(shots))

If measurements occur at the end of the :py:class:`~pytket.circuit.Circuit`, then we can associate each measurement to the qubit that was measured. :py:attr:`~pytket.circuit.Circuit.qubit_readout` gives the equivalent map to column indices for :py:class:`~pytket.unit_id.Qubit` s, and :py:attr:`~pytket.circuit.Circuit.qubit_to_bit_map` relates each measured :py:class:`~pytket.unit_id.Qubit` to the :py:class:`~pytket.unit_id.Bit` that holds the corresponding measurement result.

.. jupyter-execute::

    from pytket import Circuit, Qubit, Bit
    circ = Circuit(3, 2)
    circ.Rx(0.3, 0).CX(0, 1).CZ(1, 2)
    circ.Measure(0, 0)
    circ.Measure(2, 1)

    print(circ.bit_readout)
    print(circ.qubit_readout)
    print(circ.qubit_to_bit_map)

For more control over the bits extracted from the results, we can instead call :py:class:`~pytket.backends.Backend.get_result()`. The :py:class:`~pytket.backends.backendresult.BackendResult` object returned wraps up all the information returned from the experiment and allows it to be projected into any preferred way of viewing it. In particular, we can provide the list of :py:class:`~pytket.unit_id.Bit` s we want to look at in the shot table/counts dictionary, and given the exact permutation we want (and similarly for the permutation of :py:class:`~pytket.unit_id.Qubit` s for statevectors/unitaries).

.. jupyter-execute::

    from pytket import Circuit, Bit, Qubit
    from pytket.extensions.qiskit import AerBackend, AerStateBackend

    circ = Circuit(3)
    circ.H(0).Ry(-0.3, 2)
    state_b = AerStateBackend()
    circ = state_b.get_compiled_circuit(circ)
    handle = state_b.process_circuit(circ)

    # Make q[1] the most-significant qubit, so interesting state uses consecutive coefficients
    result = state_b.get_result(handle)
    print(result.get_state([Qubit(1), Qubit(0), Qubit(2)]))

    circ.measure_all()
    shot_b = AerBackend()
    circ = shot_b.get_compiled_circuit(circ)
    handle = shot_b.process_circuit(circ, n_shots=2000)
    result = shot_b.get_result(handle)

    # Marginalise out q[0] from counts
    print(result.get_counts())
    print(result.get_counts([Bit(1), Bit(2)]))

Expectation Value Calculations
------------------------------

One of the most common calculations performed with a quantum state :math:`\left| \psi \right>` is to obtain an expectation value :math:`\langle \psi | H | \psi \rangle`. For many applications, the operator :math:`H` can be expressed as a tensor product of Pauli matrices, or a linear combination of these. Given any (pure quantum) :py:class:`~pytket.circuit.Circuit` and any :py:class:`~pytket.backends.Backend`, the utility methods :py:meth:`~pytket.backends.Backend.get_pauli_expectation_value()` and :py:meth:`~pytket.backends.Backend.get_operator_expectation_value()` will generate the expectation value of the state under some operator using whatever results the :py:class:`~pytket.backends.Backend` supports. This includes adding measurements in the appropriate basis (if needed by the :py:class:`~pytket.backends.Backend`), running :py:class:`~pytket.backends.Backend.get_compiled_circuit()`, and obtaining and interpreting the results. For operators with many terms, it can optionally perform some basic measurement reduction techniques to cut down the number of :py:class:`~pytket.circuit.Circuit` s actually run by measuring multiple terms with simultaneous measurements in the same :py:class:`~pytket.circuit.Circuit`.

.. jupyter-execute::

    from pytket import Circuit, Qubit
    from pytket.extensions.qiskit import AerBackend
    from pytket.partition import PauliPartitionStrat
    from pytket.pauli import Pauli, QubitPauliString
    from pytket.utils import get_pauli_expectation_value, get_operator_expectation_value
    from pytket.utils.operators import QubitPauliOperator

    circ = Circuit(3)
    circ.Rx(0.3, 0).CX(0, 1).CZ(1, 2)   # Generate the state we want to consider
    backend = AerBackend()

    zxy = QubitPauliString({
            Qubit(0) : Pauli.Z,
            Qubit(1) : Pauli.X,
            Qubit(2) : Pauli.Y})
    xzi = QubitPauliString({
            Qubit(0) : Pauli.X,
            Qubit(1) : Pauli.Z})
    op = QubitPauliOperator({
            QubitPauliString() : 0.3,
            zxy : -1,
            xzi : 1})
    print(get_pauli_expectation_value(
            circ,
            zxy,
            backend,
            n_shots=2000))
    print(get_operator_expectation_value(
            circ,
            op,
            backend,
            n_shots=2000,
            partition_strat=PauliPartitionStrat.CommutingSets))

If you want a greater level of control over the procedure, then you may wish to write your own method for calculating :math:`\langle \psi | H | \psi \rangle`. This is simple multiplication if we are given the statevector :math:`| \psi \rangle`, but is slightly more complicated for measured systems. Since each measurement projects into either the subspace of +1 or -1 eigenvectors, we can assign +1 to each ``0`` readout and -1 to each ``1`` readout and take the average across all shots. When the desired operator is given by the product of multiple measurements, the contribution of +1 or -1 is dependent on the parity (XOR) of each measurement result in that shot. ``pytket`` provides some utility functions to wrap up this calculation and apply it to either a shot table (:py:meth:`~pytket.utils.expectation_from_shots()`) or a counts dictionary (:py:meth:`~pytket.utils.expectation_from_counts()`).

.. jupyter-execute::

    from pytket import Circuit
    from pytket.extensions.qiskit import AerBackend
    from pytket.utils import expectation_from_counts

    circ = Circuit(3, 3)
    circ.Rx(0.3, 0).CX(0, 1).CZ(1, 2)   # Generate the state we want to consider

    circ.H(1)         # Want to measure expectation for Pauli ZXY
    circ.Rx(0.5, 2)   # Measure ZII, IXI, IIY separately
    circ.measure_all()

    backend = AerBackend()
    compiled_circ = backend.get_compiled_circuit(circ)
    handle = backend.process_circuit(compiled_circ, 2000)
    counts = backend.get_result(handle).get_counts()
    print(counts)
    print(expectation_from_counts(counts))

.. Obtaining indices of specific bits/qubits of interest using `bit_readout` and `qubit_readout` or `qubit_to_bit_map`, and filtering results

.. note:: :py:meth:`~pytket.utils.expectation_from_shots()` and :py:meth:`~pytket.utils.expectation_from_counts()` take into account every classical bit in the results object. If the expectation value of interest is a product of only a subset of the measurements in the :py:class:`~pytket.circuit.Circuit` (as is the case when simultaneously measuring several commuting operators), then you will want to filter/marginalise out the ignored bits when performing this calculation.

Guidance for Writing Hardware-Agnostic Code
-------------------------------------------

Writing code for experiments that can be retargeted to different :py:class:`~pytket.backends.Backend` s can be a challenge, but has many great payoffs for long-term developments. Being able to experiment with new devices and simulators helps to identify which is best for the needs of the experiment and how this changes with the experiment parameters (such as size of chemical molecule being simulated, or choice of model to train for a neural network). Being able to react to changes in device availability helps get your results faster when contesting against queues for device access or downtime for maintenance, in addition to moving on if a device is retired from live service and taking advantage of the newest devices as soon as they come online. This is especially important in the near future as there is no clear frontrunner in terms of device, manufacturer, or even fundamental quantum technology, and the rate at which they are improving performance and scale is so high that it is essential to not get left behind with old systems.

One of the major counter-arguments against developing hardware-agnostic experiments is that the manual incorporation of the target architecture's connectivity and noise characteristics into the circuit design and choice of error mitigation/detection/correction strategies obtains the optimal performance from the device. The truth is that hardware characteristics are highly variable over time, invalidating noise models after only a few hours [Wils2020]_ and requiring regular recalibration. Over the lifetime of the device, this could lead to some qubits or couplers becoming so ineffective that they are removed from the system by the providers, giving drastic changes to the connectivity and admissible circuit designs. The instability of the experiment designs is difficult to argue when the optimal performance on one of today's devices is likely to be surpassed by an average performance on another device a short time after.

We have already seen that devices and simulators will have different sets of requirements on the :py:class:`~pytket.circuit.Circuit` s they can accept and different types of results they can return, so hardware-agnosticism will not always come for free. The trick is to spot these differences and handle them on-the-fly at runtime. The design of the :py:class:`~pytket.backends.Backend` class in ``pytket`` aims to expose the fundamental requirements that require consideration for circuit design, compilation, and result interpretation in such a way that they can easily be queried at runtime to dynamically adapt the experiment procedure. All other aspects of backend interaction that are shared between different :py:class:`~pytket.backends.Backend` s are then unified for ease of integration. In practice, the constraints of the algorithm might limit the choice of :py:class:`~pytket.backends.Backend`, or we might choose to forego the ability to run on statevector simulators so that we only have to define the algorithm to calculate using counts, but we can still be agnostic within these categories.

.. Consider whether you will want to use backends with different requirements on measurements, e.g. for using both statevector simulators and real devices; maybe build state prep and measurement circuits separately

The first point in an experiment where you might have to act differently between :py:class:`~pytket.backends.Backend` s is during :py:class:`~pytket.circuit.Circuit` construction. A :py:class:`~pytket.backends.Backend` may support a non-universal fragment of the :py:class:`~pytket.circuit.Circuit` language, typically relating to their interaction with classical data -- either full interaction, no mid-circuit measurement and conditional operations, or no measurement at all for statevector and unitary simulators. If the algorithm chosen requires mid-circuit measurement, then we must sacrifice some freedom of choice of :py:class:`~pytket.backends.Backend` to accommodate this. For safety, it could be beneficial to include assertions that the :py:class:`~pytket.backends.Backend` provided meets the expectations of the algorithm.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.extensions.qiskit import AerBackend #, AerStateBackend
    from pytket.predicates import NoMidMeasurePredicate

    backend = AerBackend()      # Choose backend in one place
    # backend = AerStateBackend()   # A backend that is incompatible with the experiment

    # For algorithms using mid-circuit measurement, we can assert this is valid
    qkd = Circuit(1, 3)
    qkd.H(0).Measure(0, 0)      # Prepare a random bit in the Z basis
    qkd.H(0).Measure(0, 1).H(0) # Eavesdropper measures in the X basis
    qkd.Measure(0, 2)           # Recipient measures in the Z basis

    assert backend.supports_counts  # Using AerStateBackend would fail at this check
    assert NoMidMeasurePredicate() not in backend.required_predicates
    compiled_qkd = backend.get_compiled_circuit(qkd)
    handle = backend.process_circuit(compiled_qkd, n_shots=1000)
    print(backend.get_result(handle).get_counts())

.. note:: The same effect can be achieved by ``assert backend.valid_circuit(qkd)`` after compilation. However, when designing the compilation procedure manually, it is unclear whether a failure for this assertion would come from the incompatibility of the :py:class:`~pytket.backends.Backend` for the experiment or from the compilation failing.

Otherwise, a practical solution around different measurement requirements is to separate the design into "state circuits" and "measurement circuits". At the point of running on the :py:class:`~pytket.backends.Backend`, we can then choose to either just send the state circuit for statevector calculations or compose it with the measurement circuits to run on sampling :py:class:`~pytket.backends.Backend` s.

.. Use `supports_X` to inspect type of backend used at runtime, or look at the requirements to see if measurements/conditionals are supported

At runtime, we can check whether a particular result type is supported using the :py:attr:`Backend.supports_X` properties (such as :py:attr:`~pytket.backends.Backend.supports_counts`), whereas restrictions on the :py:class:`~pytket.circuit.Circuit` s supported can be inspected with :py:attr:`~pytket.backends.Backend.required_predicates`.

.. Compile generically, making use of `get_compiled_circuit`

Whilst the demands of each :py:class:`~pytket.backends.Backend` on the properties of the :py:class:`~pytket.circuit.Circuit` necessitate different compilation procedures, using the default compilation sequences provided with :py:class:`~pytket.backends.Backend.get_compiled_circuit` handles compiling generically.

.. All backends can `process_circuit` identically

Similarly, every :py:class:`~pytket.backends.Backend` can use :py:meth:`~pytket.backends.Backend.process_circuit` identically. Additional :py:class:`~pytket.backends.Backend`-specific arguments (such as the number of shots required or the seed for a simulator) will just be ignored if passed to a :py:class:`~pytket.backends.Backend` that does not use them.

.. Case split on retrieval again to handle statevector separately from samplers

For the final steps of retrieving and interpreting the results, it suffices to just case-split on the form of data we can retrieve again with :py:attr:`Backend.supports_X`.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.extensions.qiskit import AerBackend #, AerStateBackend
    from pytket.utils import expectation_from_counts
    import numpy as np
    
    backend = AerBackend()      # Choose backend in one place
    # backend = AerStateBackend()   # Alternative backend with different requirements and result type

    # For many algorithms, we can separate the state preparation from measurements
    circ = Circuit(2)           # Apply e^{0.135 i pi XY} to the initial state
    circ.H(0).V(1).CX(0, 1).Rz(-0.27, 1).CX(0, 1).H(0).Vdg(1)
    measure = Circuit(2, 2)     # Measure the YZ operator via YI and IZ
    measure.V(0).measure_all()

    if backend.supports_counts:
        circ.append(measure)

    circ = backend.get_compiled_circuit(circ)
    handle = backend.process_circuit(circ, n_shots=2000)

    expectation = 0
    if backend.supports_state:
        yz = np.asarray([
            [0, 0, -1j, 0],
            [0, 0, 0, 1j],
            [1j, 0, 0, 0],
            [0, -1j, 0, 0]])
        svec = backend.get_result(handle).get_state()
        expectation = np.vdot(svec, yz.dot(svec))
    else:
        counts = backend.get_result(handle).get_counts()
        expectation = expectation_from_counts(counts)

    print(expectation)


Batch Submission
----------------

.. Some devices are accessed via queues or long-latency connections; batching helps reduce the amount of time spent waiting by pipelining

Current public-access quantum computers tend to implement either a queueing or a reservation system for mediating access. Whilst the queue-based access model gives relative fairness, guarantees availability, and maximises throughput and utilisation of the hardware, it also presents a big problem to the user with regards to latency. Whenever a circuit is submitted, not only must the user wait for it to be run on the hardware, but they must wait longer for their turn before it can even start running. This can end up dominating the time taken for the overall experiment, especially when demand is high for a particular device.

We can mitigate the problem of high queue latency by batching many :py:class:`~pytket.circuit.Circuit` s together. This means that we only have to wait the queue time once, since after the first :py:class:`~pytket.circuit.Circuit` is run the next one is run immediately rather than joining the end of the queue.

.. Advisable to generate as many circuits of interest as possible, storing how to interpret the results of each one, then send them off together
.. After processing, interpret the results by querying the result handles

To maximise the benefits of batch submission, it is advisable to generate as many of your :py:class:`~pytket.circuit.Circuit` s as possible at the same time to send them all off together. This is possible when, for example, generating every measurement circuit for an expectation value calculation, or sampling several parameter values from a local neighbourhood in a variational procedure. The method :py:class:`~pytket.backends.Backend.process_circuits()` (plural) will then submit all the provided :py:class:`~pytket.circuit.Circuit` s simultaneously and return a :py:class:`~pytket.backends.resulthandle.ResultHandle` for each :py:class:`~pytket.circuit.Circuit` to allow each result to be extracted individually for interpretation. Since there is no longer a single :py:class:`~pytket.circuit.Circuit` being handled from start to finish, it may be necessary to store additional data to record how to interpret them, like the set of :py:class:`~pytket.unit_id.Bit` s to extract for each :py:class:`~pytket.circuit.Circuit` or the coefficient to multiply the expectation value by.

.. jupyter-input::

    from pytket import Circuit
    from pytket.extensions.qiskit import IBMQBackend
    from pytket.utils import expectation_from_counts

    backend = IBMQBackend("ibmq_quito")

    state = Circuit(3)
    state.H(0).CX(0, 1).CX(1, 2).X(0)

    # Compute expectation value for -0.3i ZZZ + 0.8 XZZ + 1.2 XXX
    zzz = Circuit(3, 3)
    zzz.measure_all()
    xzz = Circuit(3, 3)
    xzz.H(0).measure_all()
    xxx = Circuit(3, 3)
    xxx.H(0).H(1).H(2).measure_all()

    circ_list = []
    for m in [zzz, xzz, xxx]:
        c = state.copy()
        c.append(m)
        circ_list.append(c)

    coeff_list = [
        -0.3j,  # ZZZ
        0.8,    # XZZ
        1.2     # XXX
    ]
    circ_list = backend.get_compiled_circuits(circ_list)

    handle_list = backend.process_circuits(circ_list, n_shots=2000)
    result_list = backend.get_results(handle_list)

    expectation = 0
    for coeff, result in zip(coeff_list, result_list):
        counts = result.get_counts()
        expectation += coeff * expectation_from_counts(counts)

    print(expectation)

.. jupyter-output::

    (1.2047999999999999-0.0015000000000000013j)

.. note:: Currently, only some devices (e.g. those from IBMQ, Quantinuum and Amazon Braket) support a queue model and benefit from this methodology, though more may adopt this in future. The :py:class:`~pytket.extensions.qiskit.AerBackend` simulator and the :py:class:`~pytket.extensions.quantinuum.QuantinuumBackend` can take advantage of batch submission for parallelisation. In other cases, :py:class:`~pytket.backends.Backend.process_circuits` will just loop through each :py:class:`~pytket.circuit.Circuit` in turn.

Embedding into Qiskit
---------------------

Not only is the goal of tket to be a device-agnostic platform, but also interface-agnostic, so users are not obliged to have to work entirely in tket to benefit from the wide range of devices supported. For example, Qiskit is currently the most widely adopted quantum software development platform, providing its own modules for building and compiling circuits, submitting to backends, applying error mitigation techniques and combining these into higher-level algorithms. Each :py:class:`~pytket.backends.Backend` in ``pytket`` can be wrapped up to imitate a Qiskit backend, allowing the benefits of tket to be felt in existing Qiskit projects with minimal work.

Below we show how the :py:class:`CirqStateSampleBackend` from the ``pytket-cirq`` extension can be used with its :py:meth:`default_compilation_pass` directly in qiskit.

.. jupyter-execute::

    from qiskit.primitives import BackendSampler
    from qiskit_algorithms import Grover, AmplificationProblem
    from qiskit.circuit import QuantumCircuit

    from pytket.extensions.cirq import CirqStateSampleBackend
    from pytket.extensions.qiskit.tket_backend import TketBackend

    cirq_simulator = CirqStateSampleBackend()
    backend = TketBackend(cirq_simulator, cirq_simulator.default_compilation_pass())
    sampler_options = {"shots":1024}
    qsampler = BackendSampler(backend, options=sampler_options)

    oracle = QuantumCircuit(2)
    oracle.cz(0, 1)

    def is_good_state(bitstr):
        return sum(map(int, bitstr)) == 2

    problem = AmplificationProblem(oracle=oracle, is_good_state=is_good_state)
    grover = Grover(sampler=qsampler)
    result = grover.amplify(problem)
    print("Top measurement:", result.top_measurement)

.. note:: Since Qiskit may not be able to solve all of the constraints of the chosen device/simulator, some compilation may be required after a circuit is passed to the :py:class:`TketBackend`, or it may just be preferable to do so to take advantage of the sophisticated compilation solutions provided in ``pytket``. Upon constructing the :py:class:`TketBackend`, you can provide a ``pytket`` compilation pass to apply to each circuit, e.g. ``TketBackend(backend, backend.default_compilation_pass())``. Some experimentation may be required to find a combination of ``qiskit.transpiler.PassManager`` and ``pytket`` compilation passes that executes successfully.

.. Pytket Assistant
.. ----------------

.. Goals of the assistant
.. How to set up and push/pull results

Advanced Backend Topics
-----------------------

Simulator Support for Expectation Values
========================================

.. May be faster to apply simple expectation values within the internal representation of simulator
.. `supports_expectation`
.. Examples of Pauli and operator expectations

Some simulators will have dedicated support for fast expectation value calculations. In this special case, they will provide extra methods :py:class:`~pytket.backends.Backend.get_pauli_expectation_value()` and :py:class:`~pytket.backends.Backend.get_operator_expectation_value()`, which take a :py:class:`~pytket.circuit.Circuit` and some operator and directly return the expectation value. Again, we can check whether a :py:class:`~pytket.backends.Backend` has this feature with :py:attr:`~pytket.backends.Backend.supports_expectation`.

.. jupyter-execute::

    from pytket import Circuit, Qubit
    from pytket.extensions.qiskit import AerStateBackend
    from pytket.pauli import Pauli, QubitPauliString
    from pytket.utils.operators import QubitPauliOperator

    backend = AerStateBackend()

    state = Circuit(3)
    state.H(0).CX(0, 1).V(2)

    xxy = QubitPauliString({
        Qubit(0) : Pauli.X,
        Qubit(1) : Pauli.X,
        Qubit(2) : Pauli.Y})
    zzi = QubitPauliString({
        Qubit(0) : Pauli.Z,
        Qubit(1) : Pauli.Z})
    iiz = QubitPauliString({
        Qubit(2) : Pauli.Z})
    op = QubitPauliOperator({
        QubitPauliString() : -0.5,
        xxy : 0.7,
        zzi : 1.4,
        iiz : 3.2})

    assert backend.supports_expectation
    state = backend.get_compiled_circuit(state)
    print(backend.get_pauli_expectation_value(state, xxy))
    print(backend.get_operator_expectation_value(state, op))

Asynchronous Job Submission
===========================

.. Checking circuit status
.. Blocking on retrieval

In the near future, as we look to more sophisticated algorithms and larger problem instances, the quantity and size of :py:class:`~pytket.circuit.Circuit` s to be run per experiment and the number of shots required to obtain satisfactory precision will mean the time taken for the quantum computation could exceed that of the classical computation. At this point, the overall algorithm can be sped up by maintaining maximum throughput on the quantum device and minimising how often the quantum device is left idle whilst the classical system is determining the next :py:class:`~pytket.circuit.Circuit` s to send. This can be achieved by writing your algorithm to operate asynchronously.

The intended semantics of the :py:meth:`~pytket.backends.Backend` methods are designed to enable asynchronous execution of quantum programs whenever admissible from the underlying API provided by the device/simulator. :py:meth:`~pytket.backends.Backend.process_circuit()` and :py:meth:`~pytket.backends.Backend.process_circuits()` will submit the :py:class:`~pytket.circuit.Circuit` (s) and immediately return.

The progress can be checked by querying :py:meth:`~pytket.backends.Backend.circuit_status()`. If this returns a :py:class:`~pytket.backends.status.CircuitStatus` matching ``StatusEnum.COMPLETED``, then :py:meth:`~pytket.backends.Backend.get_X()` will obtain the results and return immediately, otherwise it will block the thread and wait until the results are available.

.. jupyter-input::

    import asyncio
    from pytket import Circuit
    from pytket.backends import StatusEnum
    from pytket.extensions.qiskit import IBMQBackend
    from pytket.utils import expectation_from_counts

    backend = IBMQBackend("ibmq_quito")

    state = Circuit(3)
    state.H(0).CX(0, 1).CX(1, 2).X(0)

    # Compute expectation value for -0.3i ZZZ + 0.8 XZZ + 1.2 XXX
    zzz = Circuit(3, 3)
    zzz.measure_all()
    xzz = Circuit(3, 3)
    xzz.H(0).measure_all()
    xxx = Circuit(3, 3)
    xxx.H(0).H(1).H(2).measure_all()
    
    circ_list = []
    for m in [zzz, xzz, xxx]:
        c = state.copy()
        c.append(m)
        circ_list.append(backend.get_compiled_circuit(c))

    coeff_list = [
        -0.3j,  # ZZZ
        0.8,    # XZZ
        1.2     # XXX
    ]

    handle_list = backend.process_circuits(circ_list, n_shots=2000)

    async def check_at_intervals(backend, handle, interval):
        while True:
            await asyncio.sleep(interval)
            status = backend.circuit_status(handle)
            if status.status in (StatusEnum.COMPLETED, StatusEnum.ERROR):
                return status

    async def expectation(backend, handle, coeff):
        await check_at_intervals(backend, handle, 5)
        counts = backend.get_result(handle).get_counts()
        return coeff * expectation_from_counts(counts)

    async def main():
        task_set = set([asyncio.create_task(expectation(backend, h, c)) for h, c in zip(handle_list, coeff_list)])
        done, pending = await asyncio.wait(task_set, return_when=asyncio.ALL_COMPLETED)
        sum = 0
        for t in done:
            sum += await t

        print(sum)

    asyncio.run(main())

.. jupyter-output::

    (1.2087999999999999-0.002400000000000002j)

In some cases you may want to end execution early, perhaps because it is taking too long or you already have all the data you need. You can use the :py:meth:`~pytket.backends.Backend.cancel()` method to cancel the job for a given :py:class:`~pytket.backends.resulthandle.ResultHandle`. This is recommended to help reduce load on the devices if you no longer need to run the submitted jobs.

.. note:: Asynchronous submission is currently available with the :py:class:`~pytket.extensions.qiskit.IBMQBackend`, :py:class:`~pytket.extensions.quantinuum.QuantinuumBackend`, :py:class:`BraketBackend` and :py:class:`~pytket.extensions.qiskit.AerBackend`. It will be extended to others in future updates.

Persistent Handles
==================

Being able to split your processing into distinct procedures for :py:class:`~pytket.circuit.Circuit` generation and result interpretation can help improve throughput on the quantum device, but it can also provide a way to split the processing between different Python sessions. This may be desirable when the classical computation to interpret the results and determine the next experiment parameters is sufficiently intensive that we would prefer to perform it offline and only reserve a quantum device once we are ready to run more. Furthermore, resuming with previously-generated results could benefit repeatability of experiments and better error-safety since the logged results can be saved and reused.

Some :py:class:`~pytket.backends.Backend` s support persistent handles, in that the :py:class:`~pytket.backends.resulthandle.ResultHandle` object can be stored and the associated results obtained from another instance of the same :py:class:`~pytket.backends.Backend` in a different session. This is indicated by the boolean ``persistent_handles`` property of the :py:class:`~pytket.backends.Backend`. Use of persistent handles can greatly reduce the amount of logging you would need to do to take advantage of this workflow.

.. jupyter-input::

    from pytket import Circuit
    from pytket.extensions.qiskit import IBMQBackend

    backend = IBMQBackend("ibmq_quito")

    circ = Circuit(3, 3)
    circ.X(1).CZ(0, 1).CX(1, 2).measure_all()
    circ = backend.get_compiled_circuit(circ)
    handle = backend.process_circuit(circ, n_shots=1000)

    # assert backend.persistent_handles
    print(str(handle))
    counts = backend.get_result(handle).get_counts()
    print(counts)

.. jupyter-output::

    ('5e8f3dcbbb7d8500119cfbf6', 0)
    {(0, 1, 1): 1000}

.. jupyter-input::

    from pytket.backends import ResultHandle
    from pytket.extensions.qiskit import IBMQBackend
    
    backend = IBMQBackend("ibmq_quito")

    handle = ResultHandle.from_str("('5e8f3dcbbb7d8500119cfbf6', 0)")
    counts = backend.get_result(handle).get_counts()
    print(counts)

.. jupyter-output::

    {(0, 1, 1): 1000}


Result Serialization
====================

When performing experiments using :py:class:`~pytket.backends.Backend` s, it is often useful to be able to easily store and retrieve the results for later analysis or backup.
This can be achieved using native serialiaztion and deserialization of :py:class:`~pytket.backends.backendresult.BackendResult` objects from JSON compatible dictionaries, using the :py:meth:`~pytket.backends.backendresult.BackendResult.to_dict()` and :py:meth:`~pytket.backends.backendresult.BackendResult.from_dict()` methods.

.. jupyter-execute::

    import tempfile
    import json
    from pytket import Circuit
    from pytket.backends.backendresult import BackendResult
    from pytket.extensions.qiskit import AerBackend

    circ = Circuit(2, 2)
    circ.H(0).CX(0, 1).measure_all()

    backend = AerBackend()
    handle = backend.process_circuit(circ, 10)
    res = backend.get_result(handle)

    with tempfile.TemporaryFile('w+') as fp:
        json.dump(res.to_dict(), fp)
        fp.seek(0)
        new_res = BackendResult.from_dict(json.load(fp))

    print(new_res.get_counts())


.. [Niel2001] Nielsen, M.A. and Chuang, I.L., 2001. Quantum computation and quantum information. Phys. Today, 54(2), p.60.
.. [Wils2020] Wilson, E., Singh, S. and Mueller, F., 2020. Just-in-time Quantum Circuit Transpilation Reduces Noise. arXiv preprint arXiv:2005.12820.
