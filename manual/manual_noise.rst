***********************************
Noise and the Quantum Circuit Model
***********************************

.. Overview

.. NISQ Devices are noisy

NISQ era devices are characterised as having high error rates, meaning the effect of running quantum circuits on these devices is that states are commonly dominated by noise. This is usually to the extent that even for circuits with very few gates, significant errors are accrued quickly enough that the returned results are unusable.


..  Compilation prioritise different mterics to minimise devic enoise

Compilation of quantum circuits does not have a unique solution. Typically compilation strategies are designed to produce quantum circuits that implement the same logical circuit with fewer total gates and so have less opportunity to accrue errors. Understanding which quantum operations will lead to excessive noise accumulation in devices can help design compilation strategies to reduce this noise. Examples of this are circuit optimistation strategies that target the removal of multi-qubit gates as they typically have worse error rates than single-qubit gates, or designing circuit routing methods that introduce fewer total swap gates when conforming circuits to some device connectivity.

..  What else can be done

Given the range of types of quantum devices available and their individual noise profiles, more precise characterisations of where noise accumulates in devices can aid in designing techniques for suppressing specific or general noise - ``pytket`` has several such techniques available.


Noise in the quantum circuit model can be viewed as the distance between the expected distribution of measurement outcomes from a quantum state and the distribution returned by the process of repeatedly sampling shots. While some compilation methods aim to reduce this distance by the optimisation of some other metric, such as the number of occurrences of a given device's multi-qubit primitives, the discussed techniques are explicitly designed to modify the returned distribution favourably by dealing directly with noise levels.


.. Noise Aware Placement, via Device and reported backend information

Noise Aware Mapping
-------------------

..  Why this is originally a problem

Many quantum devices place limits on which qubits can
interact, with these limitations being determined by the device architecture.
When compiling a circuit to run on one of these devices, the circuit
must be modified to fit the architecture, a process described in the
previous chapter under :ref:`compiler-placement` and
:ref:`compiler-routing`.

In addition, the noise present in NISQ devices typically varies across
the architecture, with different qubits and couplings experiencing
different error rates, which may also vary depending on the operation
being performed.  To complicate matters further, these characteristics
vary over time, a phenomenon commonly referred to as device drift
[White2019]_.

Some devices expose error characterisation information through
their programming interface. When available, :py:class:`~pytket.backends.Backend`
objects will populate a :py:class:`~pytket.backends.backendinfo.BackendInfo` object with this information. 

A :py:class:`~pytket.backends.backendinfo.BackendInfo` object contains a variety of characterisation information supplied by hardware providers.   
Some information, including gate error rates, is stored in attributes with specific names.


.. jupyter-input::

    from pytket.extensions.qiskit import IBMQBackend

    backend = IBMQBackend("ibmq_manila")
    print(backend.backend_info.averaged_node_gate_errors)

.. jupyter-output::

   {node[0]: 0.0002186159622502225, 
    node[1]: 0.0002839221599849252, 
    node[2]: 0.00014610243862697218, 
    node[3]: 0.00015814094160059136, 
    node[4]: 0.00013411930305754117}    

Other miscellaneous information, varying between backends, is stored in the `misc` attribute, also accessible through the :py:meth:`~pytket.backends.BackendInfo.get_misc` method.

.. jupyter-input::

    print(backend.backend_info.get_misc())

.. jupyter-output::

    dict_keys(['t1times', 't2times', 'Frequencies', 'GateTimes'])

There is typically a large variation in device noise characteristics.

.. jupyter-input::

   from pytket.circuit import Node

   print(backend.backend_info.all_node_gate_errors[Node(0)])
   print(backend.backend_info.all_node_gate_errors[Node(1)])
    
.. jupyter-output::
    
   {<OpType.noop: 55>: 0.00036435993708370417, 
    <OpType.Rz: 32>: 0.0, 
    <OpType.SX: 27>: 0.00036435993708370417, 
    <OpType.X: 19>: 0.00036435993708370417, 
    <OpType.Reset: 58>: 0.0}
    {<OpType.noop: 55>: 0.0004732035999748754, 
    <OpType.Rz: 32>: 0.0, 
    <OpType.SX: 27>: 0.0004732035999748754, 
    <OpType.X: 19>: 0.0004732035999748754, 
    <OpType.Reset: 58>: 0.0}

.. jupyter-input::
 
   print(backend.backend_info.all_edge_gate_errors)

.. jupyter-output::

   {(node[4], node[3]): {<OpType.CX: 37>: 0.01175674116384029}, 
   (node[3], node[4]): {<OpType.CX: 37>: 0.005878370581920145}, 
   (node[2], node[3]): {<OpType.CX: 37>: 0.013302220876095505}, 
   (node[3], node[2]): {<OpType.CX: 37>: 0.006651110438047753}, 
   (node[2], node[1]): {<OpType.CX: 37>: 0.022572084465386333}, 
   (node[1], node[2]): {<OpType.CX: 37>: 0.011286042232693166}, 
   (node[0], node[1]): {<OpType.CX: 37>: 0.026409836177538337}, 
   (node[1], node[0]): {<OpType.CX: 37>: 0.013204918088769169}}
   

Recall that mapping in ``pytket`` works in two phases --
first assigning logical circuit qubits to physical device qubits
(placement) and then permuting these qubits via ``OpType.SWAP``
networks (routing).  Device characteristics can inform the choices
made in both phases, by prioritising edges with lower error rates.

.. Noise-Aware placement is effective

The class :py:class:`NoiseAwarePlacement` uses characteristics stored in
:py:class:`~pytket.backends.backendinfo.BackendInfo` to find an initial placement of logical qubits on
physical qubits which minimises the error accrued during a circuit's
execution.  It achieves this by minimising the additional
``OpType.SWAP`` overhead to route circuits, as in conventional
placement, and at the same time avoiding qubits with worse error
rates. Further information on this method is available in section 7.1
of our `software overview paper
<https://iopscience.iop.org/article/10.1088/2058-9565/ab8e92>`_.

.. jupyter-input::

    from pytket.placement import NoiseAwarePlacement, GraphPlacement

    noise_placer = NoiseAwarePlacement(backend.backend_info.architecture,
                 backend.backend_info.averaged_readout_errors,
                 backend.backend_info.averaged_node_gate_errors,
                 backend.backend_info.averaged_edge_gate_errors)
                 
    graph_placer = GraphPlacement(backend.backend_info.architecture)

    circ = Circuit(3).CX(0,1).CX(0,2)

    print(backend.backend_info.architecture.coupling, '\n')

    noise_placement = noise_placer.get_placement_map(circ)
    graph_placement = graph_placer.get_placement_map(circ)

    print('NoiseAwarePlacement mapping:')
    for k, v in noise_placement.items():
        print(k, v)

    print('\nGraphPlacement mapping:')
    for k, v in graph_placement.items():
        print(k, v)


.. jupyter-output::

    [(node[0], node[1]), (node[1], node[0]), (node[1], node[2]), (node[1], node[3]), (node[2], node[1]), (node[3], node[1]), (node[3], node[4]), (node[4], node[3])]

    NoiseAwarePlacement mapping:
    q[0] node[3]
    q[1] node[1]
    q[2] node[4]

    GraphPlacement mapping:
    q[0] node[1]
    q[1] node[0]
    q[2] node[2]

Both placement methods will satisfy the device's connectivity
constraints, however looking at the device characteristics for
``ibmq_manila`` above,  we see that the placement provided by
:py:class:`NoiseAwarePlacement` is over a set of qubits with generally
better error rates.  This will produce a circuit whose output
statistics are closer to the ideal, noiseless, distribution.

.. Frame Randomisation and friends

Noise Tailoring Methods
-----------------------

.. Why Noise tailoring might be helpful

While it is not possible to efficiently characterise and suppress all device noise, it can be advantageous to transform some adverse type of noise into a less damaging type.


Coherent errors are additional unwanted unitary rotations that may appear throughout a quantum computation. Their effect can be damaging due to a possible faster rate of error accumulation than in the case of probabilistic (incoherent) errors.


Randomisation protocols can be used to tailor the form of the noise profile. By averaging the n-qubit noise channel over all elements from a group (specifically some subgroup of the full unitary group on n qubits), the resulting noise is invariant under the action of any element from this group.


For example, averaging a noise channel over the n-qubit Pauli group has the effect of producing an n-qubit stochastic Pauli channel --  this is a probabilistic linear combination of n-qubit Pauli unitary errors.


In this manner, an n-qubit coherent noise channel can be tailored into an n-qubit stochastic Pauli noise channel. For Pauli channels, the worst case error rate is similar to the average error rate, whilst for coherent noise the worst case error rate scales as a square root of the average error rate.


The ``pytket`` :py:class:`FrameRandomisation` class available in the tailoring module provides methods for using randomised protocols on generic quantum circuits. At a high level, :py:class:`FrameRandomisation` provides methods for identifying n-qubit subcircuits (or cycles) comprised of gates chosen for tailoring in some circuit of choice, and then constructing new circuits for averaging these subcircuits over some ensemble of n-qubit operators (constructed from the Kronecker product of single qubit gates referred to as 'Frame' gates). Tailored counts for a circuit of choice are then produced by running each of the new circuits through a backend with the same number of shots and then combining the returned counts.


For each cycle in the circuit, each of the ensemble's operators is prepended to the cycle and a new operator is derived to append to the cycle such that the whole unitary operation is unchanged.  When constructing a :py:class:`FrameRandomisation` object the information required to derive the correct operator to prepend must be provided through a dictionary. An example of this procedure is *randomised compilation* [Wallman2015]_.



.. jupyter-execute::

    from pytket.tailoring import FrameRandomisation
    from pytket import OpType, Circuit
    from pytket.extensions.qiskit import AerBackend

    circ = Circuit(2).X(0).CX(0,1).S(1).measure_all()
    frame_randomisation = FrameRandomisation(
        {OpType.CX}, # Set of OpType that cycles are comprised of. For a randomised circuit, the minimum number of cycles is found such that every gate with a cycle OpType is in exactly one cycle.
        {OpType.Y}, # Set of OpType frames are constructed from
        {
            OpType.CX: {(OpType.Y, OpType.Y): (OpType.X, OpType.Z)}, # Operations to prepend and append to CX respectively such that unitary is preserved i.e. Y(0).Y(1).CX(0,1).X(0).Z(1) == CX(0,1)
        },
    )

    averaging_circuits = frame_randomisation.get_all_circuits(circ)
    print('For a single gate in the averaging ensemble we return a single circuit:')
    for com in averaging_circuits[0]:
        print(com)

    print('\nWe can check that the unitary of the circuit is preserved by comparing output counts:')
    backend = AerBackend()
    print(backend.run_circuit(circ, 100).get_counts())
    print(backend.run_circuit(averaging_circuits[0], 100).get_counts())

.. preset cycle and frame gates to tailor meaningful noise

Note that the :py:class:`FrameRandomisation` procedure sandwiches each cycle between ``OpType.Barrier`` operations. This is because frame gates can be combined with adjacent rotation gates to reduce gate overhead, but can not be commuted through their associated cycle as this will undo the framing process. As FrameRandomisation will lead to a blow up in the number of circuits compiled, it is recommended to run FrameRandomisation procedures after circuit optimisation techniques.


Running a randomised protocol to achieve meaningful results requires a careful choice of cycle gates and frame gates, which the above example does not make. However, the :py:class:`PauliFrameRandomisation` class is preset with cycle gates {``OpType.CX``, ``OpType.H``, ``OpType.S``} and frame gates {``OpType.X``, ``OpType.Y``, ``OpType.Z``, ``OpType.noop``} that should.

The :py:meth:`PauliFrameRandomisation.get_all_circuits` method returns circuits that tailor the noise of subcircuits comprised of cycle gates into a stochastic Pauli noise when run on a device (given some assumptions, such as additional frame gates not providing additional incoherent noise).

.. jupyter-execute::

    from pytket import Circuit
    from pytket.extensions.qiskit import AerBackend
    from pytket.tailoring import PauliFrameRandomisation

    circ = Circuit(2).X(0).CX(0,1).Rz(0.3, 1).CX(0,1).measure_all()

    pauli_frame_randomisation = PauliFrameRandomisation()
    averaging_circuits = pauli_frame_randomisation.get_all_circuits(circ)

    print('Number of PauliFrameRandomisation averaging circuits: ', len(averaging_circuits))

    print('\nAn example averaging circuit with frames applied to two cycles: ')
    for com in averaging_circuits[3].get_commands():
        print(com)
    print('\n')

    backend = AerBackend()

    averaging_circuits = backend.get_compiled_circuits(averaging_circuits)
    circ = backend.get_compiled_circuit(circ)

    pfr_counts_list = [
        res.get_counts() for res in backend.run_circuits(averaging_circuits, 50)
    ]
    # combine each averaging circuits counts into a single counts object for comparison
    pfr_counts = {}
    for counts in pfr_counts_list:
        pfr_counts = {key: pfr_counts.get(key,0) + counts.get(key,0) for key in set(pfr_counts)|set(counts)}

    print(pfr_counts)
    print(backend.run_circuit(circ, 50*len(averaging_circuits)).get_counts())


For a noise free backend, we can see that the same counts distribution is returned as expected. We can use a basic noise model based on a real device to see how a realistic noise channel can change when applying :py:class:`PauliFrameRandomisation`.

.. jupyter-input::

    from qiskit_aer.noise import NoiseModel
    from qiskit import IBMQ
    IBMQ.load_account()

    circ = Circuit(2).X(0).H(1).CX(0,1).Rz(0.3, 1).CX(0,1).measure_all()

    noisy_backend = AerBackend(NoiseModel.from_backend(IBMQ.providers()[0].get_backend('ibmq_manila')))

    averaging_circuits = pauli_frame_randomisation.get_all_circuits(circ)

    averaging_circuits = noisy_backend.get_compiled_circuits(averaging_circuits)
    circ = noisy_backend.get_compiled_circuit(circ)

    pfr_counts_list = [res.get_counts() for res in noisy_backend.run_circuits(averaging_circuits, 50)]
    pfr_counts = {}
    for counts in pfr_counts_list:
        pfr_counts = {key: pfr_counts.get(key,0) + counts.get(key,0) for key in set(pfr_counts)|set(counts)}


    print('Noiseless Counts:', AerBackend().run_circuit(circ, 50*len(averaging_circuits).get_counts()))
    print('Base Noisy Counts:', noisy_backend.run_circuit(circ, 50*len(averaging_circuits).get_counts()))
    print('Recombined Noisy Counts using PauliFrameRandomisation:', pfr_counts)


.. jupyter-output::

    Noiseless Counts: Counter({(1, 1): 6415, (1, 0): 6385})
    Base Noisy Counts: Counter({(1, 0): 6368, (1, 1): 5951, (0, 1): 253, (0, 0): 228})
    Recombined Noisy Counts using PauliFrameRandomisation: {(0, 1): 203, (0, 0): 215, (1, 0): 6194, (1, 1): 6188}


For this simple case we observe that more shots are returning basis states not in the expected state (though it would be unwise to declare the methods efficacy from this alone).


Given that cycle gates for :py:class:`PauliFrameRandomisation` do not form a universal gate set for the quantum circuit model, randomised protocols using :py:class:`PauliFrameRandomisation` will usually need to individually tailor many cycle instances for a given circuit. This can lead to large circuit overhead required for complete averaging, or a loss of guarantee that the resulting channel is a stochastic Pauli noise when not every frame is used.


An alternative class, :py:class:`UniversalFrameRandomisation`, is set with cycle gates {``OpType.CX``, ``OpType.H``, ``OpType.Rz``} and frame gates {``OpType.X``, ``OpType.Y``, ``OpType.Z``, ``OpType.noop``} and so can treat a whole circuit as a single cycle if rebased appropriately. It providers averaging circuits  while preserving the unitary of the circuit by changing the rotation angle of cycle ``OpType.Rz`` gates when prepending and appending frame gates, meaning that the stochastic Pauli noise property is additionally dependent on incoherent noise not being dependent on the rotation angle.

.. jupyter-input::

    from pytket.tailoring import UniversalFrameRandomisation

    universal_frame_randomisation = UniversalFrameRandomisation()

    circ = Circuit(2).X(0).H(1).CX(0,1).Rz(0.3, 1).CX(0,1).measure_all()

    averaging_circuits = universal_frame_randomisation.get_all_circuits(circ)
    print()

    averaging_circuits = noisy_backend.get_compiled_circuits(averaging_circuits)
    circ = noisy_backend.get_compiled_circuit(circ)

    ufr_noisy_counts_list = [res.get_counts() for res in noisy_backend.run_circuits(averaging_circuits, 800)]
    ufr_noisy_counts = {}
    for counts in ufr_noisy_counts_list:
        ufr_noisy_counts = {key: ufr_noisy_counts.get(key,0) + counts.get(key,0) for key in set(ufr_noisy_counts)|set(counts)}


    ufr_noiseless_counts_list = [res.get_counts() for res in AerBackend().run_circuits(averaging_circuits, 800)]
    ufr_noiseless_counts = {}
    for counts in ufr_noiseless_counts_list:
        ufr_noiseless_counts = {key: ufr_noiseless_counts.get(key,0) + counts.get(key,0) for key in set(ufr_noiseless_counts)|set(counts)}


    print('Noiseless Counts:', noiseless_counts)
    print('Recombined Noiseless Counts using UniversalFrameRandomisation:', ufr_noiseless_counts)
    print('Base Noisy Counts:', noisy_counts)
    print('Recombined Noisy Counts using PauliFrameRandomisation:', pfr_counts)
    print('Recombined Noisy Counts using UniversalFrameRandomisation:', ufr_noisy_counts)


.. jupyter-output::

    Noiseless Counts: Counter({(1, 0): 6490, (1, 1): 6310})
    Recombined Noiseless Counts using UniversalFrameRandomisation: {(1, 0): 6440, (1, 1): 6360}
    Base Noisy Counts: Counter({(1, 0): 6298, (1, 1): 6022, (0, 1): 261, (0, 0): 219})
    Recombined Noisy Counts using PauliFrameRandomisation: {(0, 1): 240, (0, 0): 212, (1, 0): 6253, (1, 1): 6095}
    Recombined Noisy Counts using UniversalFrameRandomisation: {(0, 1): 208, (0, 0): 208, (1, 0): 6277, (1, 1): 6107}

Similarly as to the previous case, more shots are returning basis states in the expected state.

We can use :py:meth:`auto_rebase_pass` to create a pass that can be applied to a circuit to rebase its gates to {``OpType.CX``, ``OpType.H``, ``OpType.Rz``}, the cycle gate primitives for Universal Frame Randomisation.

.. jupyter-execute::

    from pytket.circuit import PauliExpBox, Pauli, Circuit, OpType
    from pytket.transform import Transform
    from pytket.passes import auto_rebase_pass
    from pytket.tailoring import UniversalFrameRandomisation

    rebase_ufr = auto_rebase_pass({OpType.CX, OpType.H, OpType.Rz})

    universal_frame_randomisation = UniversalFrameRandomisation()

    circ = Circuit(4)
    circ.X(0)
    circ.X(1)
    circ.add_pauliexpbox(
        PauliExpBox([Pauli.X, Pauli.Z, Pauli.Y, Pauli.I], 0.034), [0, 1, 2, 3]
    )
    circ.add_pauliexpbox(
        PauliExpBox([Pauli.Y, Pauli.Z, Pauli.X, Pauli.I], -0.2), [0, 1, 2, 3]
    )
    circ.add_pauliexpbox(
        PauliExpBox([Pauli.I, Pauli.X, Pauli.Z, Pauli.Y], 0.45), [0, 1, 2, 3]
    )

    Transform.DecomposeBoxes().apply(circ)
    ufr_averaging_circuits = universal_frame_randomisation.get_all_circuits(circ)
    print('Number of Universal Frame Randomisation averaging circuits without rebase: ', len(ufr_averaging_circuits))

    rebase_ufr.apply(circ)
    ufr_averaging_circuits = universal_frame_randomisation.get_all_circuits(circ)
    print('Number of Universal Frame Randomisation averaging circuits with rebase: ', len(ufr_averaging_circuits))

    ufr_averaging_circuits = universal_frame_randomisation.sample_circuits(circ, 200)
    print('Number of sampled Universal Frame Randomisation averaging circuits with rebase: ', len(ufr_averaging_circuits))


By rebasing the circuit Universal Frame Randomisation is being applied to, we can see a significant reduction in the number of averaging circuits required. For large circuits with many cycles :py:meth:`FrameRandomisation.sample_circuits`
can be used to sample from the full set of averaging circuits. It is recommended to use :py:meth:`FrameRandomisation.sample_circuit` over :py:meth:`FrameRandomisation.get_all_circuits` for larger circuits with many cycles as the overhead in finding frame permutations becomes significant.

.. SPAM Mitigation module and how to use

SPAM Mitigation
---------------


A prominent source of noise is that occurring during State Preparation and Measurement (SPAM) in the hardware.

SPAM error mitigation methods can correct for such noise through a post-processing step that modifies the output distribution measured from repeatedly sampling shots. This is possible given the assumption that SPAM noise is not dependent on the quantum computation run.

By repeatedly preparing and measuring a basis state of the device, a distribution over basis states is procured. While for a perfect device the distribution would be the prepared basis state with probability 1, for devices prone to SPAM noise this distribution is perturbed and other basis states may be returned with (expected) small probability.

If this process is repeated for all (or a suitable subset given many qubits won't experience correlated SPAM errors) basis states of a device, a transition matrix can be derived that describes the noisy SPAM process.
Simply applying the inverse of this transition matrix to the distribution of a quantum state from some desired quantum computation can effectively uncompute the errors caused by SPAM noise.

The :py:class:`SpamCorrecter` provides the required tools for characterising and correcting SPAM noise in this manner. A :py:class:`SpamCorrecter` object is initialised from a partition of a subset of the quantum device's qubits. Qubits are assumed to have SPAM errors which are correlated with that of other qubits in their set, but uncorrelated with the other sets.

As an n-qubit device has :math:`2^n` basis states, finding the exact noisy SPAM process becomes infeasible for larger devices. However, as correlated errors are typically spatially dependent though, one can usually characterise SPAM noise well by only assuming correlated SPAM noise between nearest-neighbour qubits.

The :py:class:`SpamCorrecter` object uses these subsets of qubits to produce calibration circuits.


.. jupyter-input::

    from pytket.utils.spam import SpamCorrecter
    from pytket.extensions.qiskit import IBMQBackend

    backend = IBMQBackend("ibmq_quito")
    nodes = backend.backend_info.architecture.nodes

    spam_correcter = SpamCorrecter([nodes])

    calibration_circuits = spam_correcter.calibration_circuits()
    print('Number of calibration circuits: ' , len(calibration_circuits))
    print(calibration_circuits[1].get_commands())


.. jupyter-output::

    Number of calibration circuits:  32

    [X node[4];, Barrier node[0], node[1], node[2], node[3], node[4];, Measure node[0] --> c[0];, Measure node[1] --> c[1];, Measure node[2] --> c[2];, Measure node[3] --> c[3];, Measure node[4] --> c[4];]



Assuming SPAM correlation between all 5 qubits of the "ibmq_quito" device, there are a total of 32 calibration circuits total for constructing each basis state. Printing the commands of the second basis state preparation circuit, we see that the circuits simply apply X gates to the states of qubits initialised in the 0 state as appropriate.

To display the performance of SPAM correction in a controlled environment, we can construct a noise model with measurement errors from ``qiskit-aer`` and use it to define a simulator backend with known measurement noise.

First the :py:class:`SpamCorrecter` is characterised using counts results for calibration circuits executed through the noisy backend of choice using :py:meth:`SpamCorrecter.calculate_matrices`. Once characterised, noisy counts for a circuit can be corrected using :py:meth:`SpamCorrecter.correct_counts`.

.. jupyter-execute::

    from pytket.extensions.qiskit import AerBackend
    from pytket import Circuit
    from pytket.utils.spam import SpamCorrecter

    from qiskit_aer.noise import NoiseModel
    from qiskit_aer.noise.errors import depolarizing_error

    noise_model = NoiseModel()
    noise_model.add_readout_error([[0.9, 0.1],[0.1, 0.9]], [0])
    noise_model.add_readout_error([[0.95, 0.05],[0.05, 0.95]], [1])
    noise_model.add_quantum_error(depolarizing_error(0.1, 2), ["cx"], [0, 1])

    noisy_backend = AerBackend(noise_model)
    noiseless_backend = AerBackend()
    spam_correcter = SpamCorrecter([noisy_backend.backend_info.architecture.nodes], noisy_backend)
    calibration_circuits = spam_correcter.calibration_circuits()

    char_handles = noisy_backend.process_circuits(calibration_circuits, 1000)
    char_results = noisy_backend.get_results(char_handles)

    spam_correcter.calculate_matrices(char_results)

    circ = Circuit(2).H(0).CX(0,1).measure_all()
    circ = noisy_backend.get_compiled_circuit(circ)
    noisy_handle = noisy_backend.process_circuit(circ, 1000)
    noisy_result = noisy_backend.get_result(noisy_handle)
    noiseless_handle = noiseless_backend.process_circuit(circ, 1000)
    noiseless_result = noiseless_backend.get_result(noiseless_handle)
    
    circ_parallel_measure = spam_correcter.get_parallel_measure(circ)
    corrected_counts = spam_correcter.correct_counts(noisy_result, circ_parallel_measure)

    print('Noisy Counts:', noisy_result.get_counts())
    print('Corrected Counts:', corrected_counts.get_counts())
    print('Noiseless Counts:', noiseless_result.get_counts())


Despite the presence of additional noise, it is straightforward to see that the corrected counts results are closer to the expected noiseless counts than the original noisy counts. All that is required to use :py:class:`SpamCorrecter` with a real device is the interchange of :py:class:`~pytket.extensions.qiskit.AerBackend` with a real device backend, such as  :py:class:`~pytket.extensions.qiskit.IBMQBackend`.







.. [Wallman2015] Wallman, J., Emerson, J., 2015. Noise tailoring for scalable quantum computation via randomized compiling. Phys. Rev. A 94, 052325 (2016).

.. [White2019] White, G., Hill, C., Hollenberg, L., 2019. Performance optimisation for drift-robust fidelity improvement of two-qubit gates. arXiv:1911.12096.




