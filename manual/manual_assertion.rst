***********************************
Assertion
***********************************

In quantum computing, an assertion is a predefined predicate which can let us test whether an experimentally prepared quantum state is in a specified subspace of the state space.

In addition to detecting defects, the assertion schemes in ``pytket`` automatically correct the state if there is no assertion error.
This property can be potentially exploited to help error mitigation or nondeterministically preparing a quantum state.

``pytket`` provides two ways to construct an assertion, by a projector matrix or by a set of Pauli stabilisers.
The former can be used to assert arbitrary subspaces, but note that we currently only support 2x2, 4x4, and 8x8 matrices.
The latter is useful for asserting that the prepared state lies in a subspace spanned by some stabiliser states.

When applied to a circuit, the assertion is inserted as a :py:class:`~pytket.circuit.ProjectorAssertionBox` or a :py:class:`~pytket.circuit.StabiliserAssertionBox`, and then synthesized into a set of gates and measurements by the :py:class:`~pytket.passes.DecomposeBoxes` pass. Be aware that an ancilla qubit might be required for the assertion.
The results of these measurements will be used later on to determine the outcome of the assertion.

To test the circuit, compile and process the circuit using a :py:class:`~pytket.backends.Backend` that supports mid-circuit measurement and reset (e.g. :py:class:`~pytket.extensions.qiskit.AerBackend` from ``pytket-qiskit``).
Once a :py:class:`~pytket.backends.backendresult.BackendResult` object is retrieved, the outcome of the assertion can be checked with the :py:meth:`~pytket.backends.backendresult.BackendResult.get_debug_info` method.


Projector-based
---------------

Projector-based assertion utilises the simple fact that the outcome of a projective measurement can be used to determine if a quantum state is in a specified subspace of the state space.
The method implemented in pytket transforms an arbitrary projective measurement into measurements on the computational basis [Gushu2020]_. 
However, this approach is not without limitations. Projectors in general require :math:`2^{n} \times 2^{n}` matrices to represent them; hence it becomes impractical when the size of the asserted subspace is large.
Moreover, the transformation technique we have adapted requires synthesis for arbitrary unitary matrices. Since ``pytket`` currently only supports synthesis for 1, 2, and 3 qubit unitaries, the projectors are limited to 2x2, 4x4, and 8x8 matrices.

To start asserting with a projector, one should first compute the projector matrix for the target subspace. If the rank of the projector is larger than :math:`2^{n-1}` (:math:`n` is the number of qubits), an ancilla qubit should be provided to the :py:meth:`~pytket.circuit.Circuit.add_assertion()` method.
A special unsupported case arises when asserting a 3-qubit subspace whose projector has a rank larger than :math:`2^{3-1}`.

In the following example, we try to prepare a Bell state along with a state obtained by applying an :math:`\mathrm{Rx}(0.3)` rotation to :math:`|0\rangle`; we then use projectors to assert that the circuit construction is correct.

.. jupyter-execute::

    from pytket.circuit import ProjectorAssertionBox, Circuit
    from pytket.extensions.qiskit import AerBackend
    import numpy as np
    import math

    # construct a circuit that prepares a Bell state for qubits [0,1]
    # and a Rx(0.3)|0> state for qubit 2
    circ = Circuit(3)
    circ.H(0).CX(0,1).Rx(0.03,2)    # A bug in the circuit

    # prepare a backend
    backend = AerBackend()

    # prepare a projector for the Bell state
    bell_projector = np.array([
        [0.5, 0, 0, 0.5],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0.5, 0, 0, 0.5],
    ])
    # prepare a projector for the state Rx(0.3)|0>
    rx_projector = np.array([
        [math.cos(0.15*math.pi) ** 2, 0.5j*math.sin(0.3*math.pi)],
        [-0.5j*math.sin(0.3*math.pi), math.sin(0.15*math.pi) ** 2]
    ])

    # add the assertions
    circ.add_assertion(ProjectorAssertionBox(bell_projector), [0,1], name="|bell>")
    circ.add_assertion(ProjectorAssertionBox(rx_projector), [2], name="Rx(0.3)|0>")

    # compile and run the circuit
    compiled_circ = backend.get_compiled_circuit(circ)
    res_handle = backend.process_circuit(compiled_circ,n_shots=100)
    re = backend.get_result(res_handle)
    re.get_debug_info()

Without the presence of noise, if a state is in the target subspace, then its associated assertion will succeed with certainty; on the other hand, an assertion failure indicates that the state is not in the target subspace.
In order to really test the program, the debug circuit should be run multiple times to ensure an accurate conclusion. The :py:class:`dict` object returned by :py:meth:`~pytket.backends.backendresult.BackendResult.get_debug_info` suggests that the Bell state assertion succeeded for all the 100 shots; hence we are confident that the construction for the Bell state is correct.
On the contrary, the assertion named "Rx(0.3)|0>" failed for some shots; this means that the construction for that state is incorrect.

If there is noise in the device, which is the case for all devices in the NISQ era, then the results can be much less clear. The following example demonstrates what the assertion outcome will look like if we compile and run the debug circuit with a noisy backend.


.. jupyter-input::

    from qiskit_aer.noise import NoiseModel
    from qiskit import IBMQ
    IBMQ.load_account()

    # prepare a noisy backend
    backend = AerBackend(NoiseModel.from_backend(IBMQ.providers()[0].get_backend('ibmq_manila')))

    # compile the previously constructed circuit
    compiled_circ = backend.get_compiled_circuit(circ)
    res_handle = backend.process_circuit(compiled_circ,n_shots=100)
    re = backend.get_result(res_handle)
    re.get_debug_info()

.. jupyter-output::

    {'|bell>': 0.95, '|Rx(0.3)>': 0.98}


Stabiliser-based
--------------------------

A stabiliser subspace is a subspace that can be uniquely determined by a stabiliser subgroup.
Since all Pauli operators in a stabiliser subgroup have +/- 1 eigenvalues, we can verify if a quantum state is in the +1 eigenspace of such a Pauli operator by repeatedly measuring the following circuit [Niel2010]_.

.. jupyter-execute::
    :hide-code:

    from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
    from qiskit.circuit.library.standard_gates import HGate, XGate

    qc = QuantumCircuit(2,1)
    qc.h(0)
    u = XGate("Pauli operator").control(1)
    qc.append(u, [0,1])
    qc.h(0)
    qc.measure([0], [0])
    qc.draw()

To verify if a quantum state is in a stabiliser subspace such a circuit is needed for each Pauli operator so they can be later measured to check if the state falls into the intersection of the +1 eigenspaces.

To assert using stabilisers, one should provide ``pytket`` with a set of Pauli operators that uniquely determines the target subspace. The smallest such sets are the generating sets of the stabiliser subgroup stabilising the subspace.
These generating sets only contain at most :math:`n` Pauli operators for a n-qubit subspace. For example, it is known that the set {"XX", "ZZ"} is a generating set for the stabiliser subgroup that stabilises the Bell state.

The following code demonstrates how we use the generating set for the Bell state to assert a circuit construction.

.. jupyter-execute::

    from pytket.circuit import StabiliserAssertionBox, Circuit, Qubit
    from pytket.extensions.qiskit import AerBackend

    # prepare a Bell state
    circ = Circuit(2)
    circ.H(0).CX(0,1)

    # add an ancilla qubit for this assertion
    circ.add_qubit(Qubit(2))

    # define the generating set
    stabilisers = ["XX", "ZZ"]

    circ.add_assertion(StabiliserAssertionBox(stabilisers), [0,1], ancilla=2, name="|bell>")

    backend = AerBackend()
    compiled_circ = backend.get_compiled_circuit(circ)
    res_handle = backend.process_circuit(compiled_circ,n_shots=100)
    res = backend.get_result(res_handle)
    res.get_debug_info()


A :py:class:`~pytket.circuit.StabiliserAssertionBox` can also be constructed with a :py:class:`~pytket.pauli.PauliStabiliser`:

.. jupyter-execute::

    from pytket.pauli import PauliStabiliser, Pauli

    stabilisers = [PauliStabiliser([Pauli.X, Pauli.X], 1), PauliStabiliser([Pauli.Z, Pauli.Z], 1)]
    s = StabiliserAssertionBox(stabilisers)


.. [Gushu2020] Gushu, L., Li, Z., Nengkun, Y., Yufei, D., Mingsheng, Y. and Yuan, X., 2020. Proq: Projection-based Runtime Assertions for Debugging on a Quantum Computer. arXiv preprint arXiv:1911.12855.
.. [Niel2010] Nielsen, M.A. and Chuang, I.L., 2010. Quantum computation and quantum information. Cambridge University Press, p.188.
