***********
Compilation
***********

So far, we have already covered enough to be able to design the :py:class:`Circuit` s we want to run, submit them to a :py:class:`Backend`, and interpret the results in a meaningful way. This is all you need if you want to just try out a quantum computer, run some toy examples and observe some basic results. We actually glossed over a key step in this process by using the :py:meth:`Backend.get_compiled_circuit()` method. The compilation step maps from the universal computer abstraction presented at :py:class:`Circuit` construction to the restricted fragment supported by the target :py:class:`Backend`, and knowing what a compiler can do to your program can help reduce the burden of design and improve performance on real devices.

The necessity of compilation maps over from the world of classical computation: it is much easier to design correct programs when working with higher-level constructions that aren't natively supported, and it shouldn't require a programmer to be an expert in the exact device architecture to achieve good performance. There are many possible low-level implementations on the device for each high-level program, which vary in the time and resources taken to execute. However, because QPUs are analog devices, the implementation can have a massive impact on the quality of the final outcomes as a result of changing how susceptible the system is to noise. Using a good compiler and choosing the methods appropriately can automatically find a better low-level implementation. Each aspect of the compilation procedure is exposed through ``pytket`` to provide users with a way to have full control over what is applied and how.

.. Optimisation/simplification and constraint solving

The primary goals of compilation are two-fold: solving the constraints of the :py:class:`Backend` to get from the abstract model to something runnable, and optimising/simplifying the :py:class:`Circuit` to make it faster, smaller, and less prone to noise. Every step in compilation can generally be split up into one of these two categories (though even the constraint solving steps could have multiple solutions over which we could optimise for noise).

.. Passes capture methods of transforming the circuit, acting in place

Each compiler pass inherits from the :py:class:`BasePass` class, capturing a method of transforming a :py:class:`Circuit`. The main functionality is built into the :py:meth:`BasePass.apply()` method, which applies the transformation to a :py:class:`Circuit` in-place. The :py:meth:`Backend.get_compiled_circuit()` method is a wrapper around the :py:meth:`BasePass.apply()` from the :py:class:`Backend` 's recommended pass sequence. This chapter will explore these compiler passes, the different kinds of constraints they are used to solve and optimisations they apply, to help you identify which ones are appropriate for a given task.

Predicates
----------

.. Predicates capture properties a circuit could satisfy
.. Primarily used to describe requirements of the backends

Solving the constraints of the target :py:class:`Backend` is the essential goal of compilation, so our choice of passes is mostly driven by this set of constraints. We already saw in the last chapter that the :py:attr:`Backend.required_predicates` property gives a collection of :py:class:`Predicate` s, describing the necessary properties a :py:class:`Circuit` must satisfy in order to be run.

Each :py:class:`Predicate` can be constructed on its own to impose tests on :py:class:`Circuit` s during construction.

.. jupyter-execute::

    from pytket import Circuit, OpType
    from pytket.predicates import GateSetPredicate, NoMidMeasurePredicate

    circ = Circuit(2, 2)
    circ.Rx(0.2, 0).CX(0, 1).Rz(-0.7, 1).measure_all()

    gateset = GateSetPredicate({OpType.Rx, OpType.CX, OpType.Rz, OpType.Measure})
    midmeasure = NoMidMeasurePredicate()

    print(gateset.verify(circ))
    print(midmeasure.verify(circ))

    circ.S(0)

    print(gateset.verify(circ))
    print(midmeasure.verify(circ))

.. Common predicates

======================================= =======================================
Common :py:class:`Predicate`            Constraint
======================================= =======================================
:py:class:`GateSetPredicate`           
                                          Every gate is within a set of allowed
                                          :py:class:`OpType` s
:py:class:`ConnectivityPredicate`       
                                          Every multi-qubit gate acts on
                                          adjacent qubits according to some
                                          connectivity graph
:py:class:`DirectednessPredicate`       
                                          Extends
                                          :py:class:`ConnectivityPredicate`
                                          where ``OpType::CX`` gates are only
                                          supported in a specific orientation
                                          between adjacent qubits
:py:class:`NoClassicalControlPredicate` 
                                          The :py:class:`Circuit` does not
                                          contain any gates that act
                                          conditionally on classical data
:py:class:`NoMidMeasurePredicate`      
                                          All ``OpType::Measure`` gates act at
                                          the end of the :py:class:`Circuit`
                                          (there are no subsequent gates on
                                          either the :py:class:`Qubit` measured
                                          or the :py:class:`Bit` written to)
======================================= =======================================

.. Pre/post-conditions of passes

When applying passes, you may find that you apply some constraint-solving pass to satisfy a particular :py:class:`Predicate`, but then a subsequent pass will invalidate it by, for example, introducing gates of different gate types or changing which qubits interact via multi-qubit gates. To help understand and manage this, each pass has a set of pre-conditions that specify the requirements assumed on the :py:class:`Circuit` in order for the pass to successfully be applied, and a set of post-conditions that specify which :py:class:`Predicate` s are guaranteed to hold for the outputs and which are invalidated or preserved by the pass. These can be viewed in the API reference for each pass.

Users may find it desirable to enforce their own constraints upon circuits they are working with. It is possible to construct a :py:class:`UserDefinedPredicate` in pytket based on a function that returns a True/False value.

Below is a minimal example where we construct a predicate which checks if our :py:class:`Circuit` contains fewer than 3 CX gates.

.. jupyter-execute::

    from pytket.circuit import Circuit, OpType
    from pytket.predicates import UserDefinedPredicate

    def max_cx_count(circ: Circuit) -> bool:
        return circ.n_gates_of_type(OpType.CX) < 3

    # Now construct our predicate using the function defined above
    my_predicate = UserDefinedPredicate(max_cx_count)

    test_circ = Circuit(2).CX(0, 1).Rz(0.25, 1).CX(0, 1) # Define a test Circuit

    my_predicate.verify(test_circ)
    # test_circ satisfies predicate as it contains only 2 CX gates

Rebases
-------

.. Description

One of the simplest constraints to solve for is the :py:class:`GateSetPredicate`, since we can just substitute each gate in a :py:class:`Circuit` with an equivalent sequence of gates in the target gateset according to some known gate decompositions. In ``pytket``, such passes are referred to as "rebases". The intention here is to perform this translation naively, leaving the optimisation of gate sequences to other passes. Rebases can be applied to any :py:class:`Circuit` and will preserve every structural :py:class:`Predicate`, only changing the types of gates used.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.passes import RebaseTket

    circ = Circuit(2, 2)
    circ.Rx(0.3, 0).Ry(-0.9, 1).CZ(0, 1).S(0).CX(1, 0).measure_all()

    RebaseTket().apply(circ)

    print(circ.get_commands())

:py:class:`RebaseTket` is a standard rebase pass that converts to CX and TK1 gates. This is the preferred internal gateset for many ``pytket`` compiler passes. However, it is possible to define a rebase for an arbitrary gateset. Using :py:class:`RebaseCustom`, we can provide an arbitrary set of one- and two-qubit gates. Rather than requiring custom decompositions to be provided for every gate type, it is sufficient to just give them for ``OpType.CX`` and ``OpType.TK1``. For any gate in a given :py:class:`Circuit`, it is either already in the target gateset, or we can use known decompositions to obtain a ``OpType.CX`` and ``OpType.TK1`` representation and then map this to the target gateset.

.. jupyter-execute::

    from pytket import Circuit, OpType
    from pytket.passes import RebaseCustom

    gates = {OpType.Rz, OpType.Ry, OpType.CY, OpType.ZZPhase}
    cx_in_cy = Circuit(2)
    cx_in_cy.Rz(0.5, 1).CY(0, 1).Rz(-0.5, 1)

    def tk1_to_rzry(a, b, c):
        circ = Circuit(1)
        circ.Rz(c + 0.5, 0).Ry(b, 0).Rz(a - 0.5, 0)
        return circ

    custom = RebaseCustom(gates, cx_in_cy, tk1_to_rzry)

    circ = Circuit(3)
    circ.X(0).CX(0, 1).Ry(0.2, 1)
    circ.add_gate(OpType.ZZPhase, -0.83, [2, 1]).Rx(0.6, 2)

    custom.apply(circ)

    print(circ.get_commands())

For some gatesets, it is not even necessary to specify the CX and TK1 decompositions: there is a useful function :py:meth:`auto_rebase_pass` which can take care of this for you. The pass returned is constructed from the gateset alone. (It relies on some known decompositions, and will raise an exception if no suitable known decompositions exist.) An example is given in the "Combinators" section below.

A similar pair of methods, :py:meth:`SquashCustom` and :py:meth:`auto_squash_pass`, may be used to construct a pass that squashes sequences of single-qubit gates from a given set of single-qubit gates to as short a sequence as possible. Both take a gateset as an argument. :py:meth:`SquashCustom` also takes a function for converting the parameters of a TK1 gate to the target gate set. (Internally, the compiler squashes all gates to TK1 and then applies the supplied function.) :py:meth:`auto_squash_pass` attempts to do the squash using known internal decompositions (but may fail for some gatesets). For example:

.. jupyter-execute::

    from pytket.circuit import Circuit, OpType
    from pytket.passes import auto_squash_pass

    gates = {OpType.PhasedX, OpType.Rz, OpType.Rx, OpType.Ry}
    custom = auto_squash_pass(gates)

    circ = Circuit(1).H(0).Ry(0.5, 0).Rx(-0.5, 0).Rz(1.5, 0).Ry(0.5, 0).H(0)
    custom.apply(circ)
    print(circ.get_commands())

Note that the H gates (which are not in the specified gateset) are left alone.


.. _compiler-placement:

Placement
---------

.. Task of selecting appropriate physical qubits to use; better use of connectivity and better noise characteristics

Initially, a :py:class:`Circuit` designed without a target device in mind will be expressed in terms of actions on a set of "logical qubits" - those with semantic meaning to the computation. A `placement` (or `initial mapping`) is a map from these logical qubits to the physical qubits of the device that will be used to carry them. A given placement may be preferred over another if the connectivity of the physical qubits better matches the interactions between the logical qubits caused by multi-qubit gates, or if the selection of physical qubits has better noise characteristics. All of the information for connectivity and noise characteristics of a given :py:class:`Backend` is wrapped up in a :py:class:`BackendInfo` object by the :py:attr:`Backend.backend_info` property.

.. Affects where the logical qubits start initially, but it not necessarily where they will end up being measured at the end

The placement only specifies where the logical qubits will be at the start of execution, which is not necessarily where they will end up on termination. Other compiler passes may choose to permute the qubits in the middle of a :py:class:`Circuit` to either exploit further optimisations or enable interactions between logical qubits that were not assigned to adjacent physical qubits.

.. Placement acts in place by renaming qubits to their physical addresses (classical data is never renamed)

A placement pass will act in place on a :py:class:`Circuit` by renaming the qubits from their logical names (the :py:class:`UnitID` s used at circuit construction) to their physical addresses (the :py:class:`UnitID` s recognised by the :py:class:`Backend`). Classical data is never renamed.

.. Basic example

.. jupyter-input::

    from pytket import Circuit
    from pytket.extensions.qiskit import IBMQBackend
    from pytket.passes import PlacementPass
    from pytket.predicates import ConnectivityPredicate
    from pytket.placement import GraphPlacement

    circ = Circuit(4, 4)
    circ.H(0).H(1).H(2).V(3)
    circ.CX(0, 1).CX(1, 2).CX(2, 3)
    circ.Rz(-0.37, 3)
    circ.CX(2, 3).CX(1, 2).CX(0, 1)
    circ.H(0).H(1).H(2).Vdg(3)
    circ.measure_all()

    backend = IBMQBackend("ibmq_quito")
    place = PlacementPass(GraphPlacement(backend.backend_info.architecture))
    place.apply(circ)

    print(circ.get_commands())
    print(ConnectivityPredicate(backend.backend_info.architecture).verify(circ))

.. jupyter-output::

    [H node[0];, H node[1];, H node[3];, V node[4];, CX node[0], node[1];, CX node[1], node[3];, CX node[3], node[4];, Rz(3.63*PI) node[4];, CX node[3], node[4];, CX node[1], node[3];, Vdg node[4];, Measure node[4] --> c[3];, CX node[0], node[1];, H node[3];, Measure node[3] --> c[2];, H node[0];, H node[1];, Measure node[0] --> c[0];, Measure node[1] --> c[1];]
    True

In this example, the placement was able to find an exact match for the connectivity onto the device.

.. Sometimes best location is not determined and left to later compilation, leaving partial placement; indicated by "unplaced" register

In some circumstances, the best location is not fully determined immediately and is deferred until later in compilation. This gives rise to a partial placement (the map from logical qubits to physical qubits is a partial function, where undefined qubits are renamed into an ``unplaced`` register).

.. jupyter-input::

    from pytket import Circuit
    from pytket.extensions.qiskit import IBMQBackend
    from pytket.passes import PlacementPass
    from pytket.placement import LinePlacement

    circ = Circuit(4)
    circ.CX(0, 1).CX(0, 2).CX(1, 2).CX(3, 2).CX(0, 3)

    backend = IBMQBackend("ibmq_quito")
    place = PlacementPass(LinePlacement(backend.backend_info.architecture))
    place.apply(circ)

    print(circ.get_commands())

.. jupyter-output::

    [CX node[2], node[1];, CX node[2], node[3];, CX node[1], node[3];, CX unplaced[0], node[3];, CX node[2], unplaced[0];]

.. Define custom placement by providing qubit map

A custom (partial) placement can be applied by providing the appropriate qubit map.

.. jupyter-execute::

    from pytket.circuit import Circuit, Qubit, Node
    from pytket.placement import Placement

    circ = Circuit(4)
    circ.CX(0, 1).CX(0, 2).CX(1, 2).CX(3, 2).CX(0, 3)

    q_map = {Qubit(0) : Node(3), Qubit(2) : Node(1)}
    Placement.place_with_map(circ, q_map)

    print(circ.get_commands())

A custom placement may also be defined as a pass (which can then be combined with others to construct a more complex pass).

.. jupyter-execute::

    from pytket.circuit import Circuit, Qubit, Node
    from pytket.passes import RenameQubitsPass

    circ = Circuit(4)
    circ.CX(0, 1).CX(0, 2).CX(1, 2).CX(3, 2).CX(0, 3)

    q_map = {Qubit(0) : Qubit("z", 0), Qubit(2) : Qubit("z", 1)}
    rename = RenameQubitsPass(q_map)
    rename.apply(circ)

    print(circ.get_commands())

.. Existing heuristics: trivial (all "unplaced"), line, graph, noise

Several heuristics have been implemented for identifying candidate placements. For example, :py:class:`LinePlacement` will try to identify long paths on the connectivity graph which could be treated as a linear nearest-neighbour system. :py:class:`GraphPlacement` will try to identify a subgraph isomorphism between the graph of interacting logical qubits (up to some depth into the :py:class:`Circuit`) and the connectivity graph of the physical qubits. Then :py:class:`NoiseAwarePlacement` extends this to break ties in equivalently good graph maps by looking at the error rates of the physical qubits and their couplers. The latter two can be configured using e.g. :py:meth:`GraphPlacement.modify_config()` to change parameters like how far into the :py:class:`Circuit` it will look for interacting qubits (trading off time spent searching for the chance to find a better placement).

.. jupyter-input::

    from pytket import Circuit
    from pytket.extensions.qiskit import IBMQBackend
    from pytket.passes import PlacementPass
    from pytket.predicates import ConnectivityPredicate
    from pytket.placement import GraphPlacement

    circ = Circuit(5)
    circ.CX(0, 1).CX(1, 2).CX(3, 4)
    circ.CX(0, 1).CX(1, 2).CX(3, 4)
    circ.CX(0, 1).CX(1, 2).CX(3, 4)
    circ.CX(0, 1).CX(1, 2).CX(3, 4)
    circ.CX(0, 1).CX(1, 2).CX(3, 4)
    circ.CX(1, 4)   # Extra interaction hidden at higher depth than cutoff

    backend = IBMQBackend("ibmq_quito")
    g_pl = GraphPlacement(backend.backend_info.architecture)
    connected = ConnectivityPredicate(backend.backend_info.architecture)

    PlacementPass(g_pl).apply(circ)
    print(connected.verify(circ))   # Imperfect placement because the final CX was not considered

    # Default depth limit is 5, but there is a new interaction at depth 11
    g_pl.modify_config(depth_limit=11)

    PlacementPass(g_pl).apply(circ)
    print(connected.verify(circ))   # Now have an exact placement

.. jupyter-output::

    False
    True

.. _compiler-routing:

Mapping
-------

.. Heterogeneous architectures and limited connectivity
.. Far easier to program correctly when assuming full connectivity

The heterogeneity of quantum architectures and limited connectivity of their qubits impose the strict restriction that multi-qubit gates are only allowed between specific pairs of qubits. Given it is far easier to program a high-level operation which is semantically correct and meaningful when assuming full connectivity, a compiler will have to solve this constraint. In general, there won't be an exact subgraph isomorphism between the graph of interacting logical qubits and the connected physical qubits, so this cannot be solved with placement alone.

.. Invalid interactions between non-local qubits can be sovled by moving qubits to adjacent positions or by performing a distributed operation using the intervening qubits
.. Routing takes a placed circuit and finds non-local operations, inserting operations to fix them

One solution here, is to scan through the :py:class:`Circuit` looking for invalid interactions. Each of these can be solved by either moving the qubits around on the architecture by adding ``OpType.SWAP`` gates until they are in adjacent locations, or performing a distributed entangling operation using the intervening qubits (such as the "bridged-CX" ``OpType.BRIDGE`` which uses 4 CX gates and a single shared neighbour). The `routing` procedure used in the ``pytket`` ``RoutingPass`` takes a placed :py:class:`Circuit` and inserts gates to reduce non-local operations to sequences of valid local ones.

.. jupyter-input::

    from pytket import Circuit
    from pytket.extensions.qiskit import IBMQBackend
    from pytket.passes import PlacementPass, RoutingPass
    from pytket.placement import GraphPlacement

    circ = Circuit(4)
    circ.CX(0, 1).CX(0, 2).CX(1, 2).CX(3, 2).CX(0, 3)
    backend = IBMQBackend("ibmq_quito")
    PlacementPass(GraphPlacement(backend.backend_info.architecture)).apply(circ)
    print(circ.get_commands())  # One qubit still unplaced
                                # node[0] and node[2] are not adjacent

    RoutingPass(backend.backend_info.architecture).apply(circ)
    print(circ.get_commands())

.. jupyter-output::

    [CX node[1], node[0];, CX node[1], node[2];, CX node[0], node[2];, CX unplaced[0], node[2];, CX node[1], unplaced[0];]
    [CX node[1], node[0];, CX node[1], node[2];, SWAP node[0], node[1];, CX node[1], node[2];, SWAP node[1], node[3];, CX node[1], node[2];, CX node[0], node[1];]

.. Given partial placements, selects physical qubits on the fly
.. Due to swap insertion, logical qubits may be mapped to different physical qubits at the start and end of the circuit

As shown here, if a partial placement is used, the routing procedure will allocate the remaining qubits dynamically. We also see that the logical qubits are mapped to different physical qubits at the start and end because of the inserted ``OpType.SWAP`` gates, such as ``q[1]`` starting at ``node[0]`` and ending at ``node[3]``.

.. Other Routing options

``RoutingPass`` only provides the default option for mapping to physical circuits. The decision making used in Routing is defined in the ``RoutgMethod`` class and the choice of ``RoutingMethod`` used can be defined in the ``FullMappingPass`` compiler pass for producing physical circuits.

Decomposing Structures
----------------------

.. Box structures for high-level operations need to be mapped to low-level gates
.. Unwraps `CircuitBox`es, decomposes others into known, efficient patterns

The numerous Box structures in ``pytket`` provide practical abstractions for high-level operations to assist in :py:class:`Circuit` construction, but need to be mapped to low-level gates before we can run the :py:class:`Circuit`. The :py:class:`DecomposeBoxes` pass will unwrap any :py:class:`CircBox`, substituting it for the corresponding :py:class:`Circuit`, and decompose others like the :py:class:`Unitary1qBox` and :py:class:`PauliExpBox` into efficient templated patterns of gates.

.. jupyter-execute::

    from pytket.circuit import Circuit, CircBox, PauliExpBox
    from pytket.passes import DecomposeBoxes
    from pytket.pauli import Pauli

    sub = Circuit(2)
    sub.CZ(0, 1).T(0).Tdg(1)
    sub_box = CircBox(sub)
    circ = Circuit(4)
    circ.Rx(0.42, 2).CX(2, 0)
    circ.add_gate(sub_box, [0, 1])
    circ.add_gate(sub_box, [2, 3])
    circ.add_gate(PauliExpBox([Pauli.X, Pauli.Y, Pauli.Y, Pauli.Y], 0.2), [0, 1, 2, 3])

    DecomposeBoxes().apply(circ)
    print(circ.get_commands())

.. This could introduce undetermined structures to the circuit, invalidating gate set, connectivity, and other crucial requirements of the backend, so recommended to be performed early in the compilation procedure, allowing for these requirements to be solved again

Unwrapping Boxes could introduce arbitrarily complex structures into a :py:class:`Circuit` which could possibly invalidate almost all :py:class:`Predicate` s, including :py:class:`GateSetPredicate`, :py:class:`ConnectivityPredicate`, and :py:class:`NoMidMeasurePredicate`. It is hence recommended to apply this early in the compilation procedure, prior to any pass that solves for these constraints.

Optimisations
-------------

Having covered the primary goal of compilation and reduced our :py:class:`Circuit` s to a form where they can be run, we find that there are additional techniques we can use to obtain more reliable results by reducing the noise and probability of error. Most :py:class:`Circuit` optimisations follow the mantra of "fewer expensive resources gives less opportunity for noise to creep in", whereby if we find an alternative :py:class:`Circuit` that is observationally equivalent in a perfect noiseless setting but uses fewer resources (gates, time, ancilla qubits) then it is likely to perform better in a noisy context (though not always guaranteed).

.. Generic peephole - "looking for specific patterns of gates"; may take into account local commutations
.. Examples describing `RemoveRedundancies`, `EulerAngleReduction`, `KAKDecomposition`, and `CliffordSimp`

If we have two :py:class:`Circuit` s that are observationally equivalent, we know that replacing one for the other in any context also gives something that is observationally equivalent. The simplest optimisations will take an inefficient pattern, find all matches in the given :py:class:`Circuit` and replace them by the efficient alternative. A good example from this class of `peephole` optimisations is the :py:class:`RemoveRedundancies` pass, which looks for a number of easy-to-spot redundant gates, such as zero-parameter rotation gates, gate-inverse pairs, adjacent rotation gates in the same basis, and diagonal rotation gates followed by measurements.

.. jupyter-execute::

    from pytket import Circuit, OpType
    from pytket.passes import RemoveRedundancies

    circ = Circuit(3, 3)
    circ.Rx(0.92, 0).CX(1, 2).Rx(-0.18, 0)  # Adjacent Rx gates can be merged
    circ.CZ(0, 1).Ry(0.11, 2).CZ(0, 1)      # CZ is self-inverse
    circ.add_gate(OpType.XXPhase, 0.6, [0, 1])
    circ.add_gate(OpType.YYPhase, 0, [0, 1])    # 0-angle rotation does nothing
    circ.add_gate(OpType.ZZPhase, -0.84, [0, 1])
    circ.Rx(0.03, 0).Rz(-0.9, 1).measure_all()  # Effect of Rz is eliminated by measurement

    RemoveRedundancies().apply(circ)
    print(circ.get_commands())

It is understandable to question the relevance of such an optimisation, since a sensible programmer would not intentionally write a :py:class:`Circuit` with such redundant gates. These are still largely useful because other compiler passes might introduce them, such as routing adding a ``OpType.SWAP`` gate immediately following a ``OpType.SWAP`` gate made by the user, or commuting a Z-rotation through the control of a CX which allows it to merge with another Z-rotation on the other side.

Previous iterations of the :py:class:`CliffordSimp` pass would work in this way as well, looking for specific sequences of Clifford gates where we could reduce the number of two-qubit gates. This has since been generalised to spot these patterns up to gate commutations and changes of basis from single-qubit Clifford rotations.

.. jupyter-execute::

    from pytket import Circuit, OpType
    from pytket.passes import CliffordSimp

    # A basic inefficient pattern can be reduced by 1 CX
    simple_circ = Circuit(2)
    simple_circ.CX(0, 1).S(1).CX(1, 0)

    CliffordSimp().apply(simple_circ)
    print(simple_circ.get_commands())

    # The same pattern, up to commutation and local Clifford algebra
    complex_circ = Circuit(3)
    complex_circ.CX(0, 1)
    complex_circ.Rx(0.42, 1)
    complex_circ.S(1)
    complex_circ.add_gate(OpType.YYPhase, 0.96, [1, 2])  # Requires 2 CXs to implement
    complex_circ.CX(0, 1)

    CliffordSimp().apply(complex_circ)
    print(complex_circ.get_commands())

The next step up in scale has optimisations based on optimal decompositions of subcircuits over :math:`n`-qubits, including :py:class:`EulerAngleReduction` for single-qubit unitary chains (producing three rotations in a choice of axes), and :py:class:`KAKDecomposition` for two-qubit unitaries (using at most three CXs and some single-qubit gates).

.. jupyter-execute::

    from pytket import Circuit, OpType
    from pytket.passes import EulerAngleReduction, KAKDecomposition

    circ = Circuit(2)
    circ.CZ(0, 1)
    circ.Rx(0.4, 0).Ry(0.289, 0).Rx(-0.34, 0).Ry(0.12, 0).Rx(-0.81, 0)
    circ.CX(1, 0)

    # Reduce long chain to a triple of Ry, Rx, Ry
    EulerAngleReduction(OpType.Rx, OpType.Ry).apply(circ) 
    print(circ.get_commands())

    circ = Circuit(3)
    circ.CX(0, 1)
    circ.CX(1, 2).Rx(0.3, 1).CX(1, 2).Rz(1.5, 2).CX(1, 2).Ry(-0.94, 1).Ry(0.37, 2).CX(1, 2)
    circ.CX(1, 0)

    # Reduce long 2-qubit subcircuit to at most 3 CXs
    KAKDecomposition().apply(circ)
    print(circ.get_commands())

.. Situational macroscopic - identifies large structures in circuit or converts circuit to alternative algebraic representation; use properties of the structures to find simplifications; resynthesise into basic gates
.. Examples describing `PauliSimp`

All of these so far are generic optimisations that work for any application, but only identify local redundancies since they are limited to working up to individual gate commutations. Other techniques instead focus on identifying macroscopic structures in a :py:class:`Circuit` or convert it entirely into an alternative algebraic representation, and then using the properties of the structures/algebra to find simplifications and resynthesise into basic gates. For example, the :py:class:`PauliSimp` pass will represent the entire :py:class:`Circuit` as a sequence of exponentials of Pauli operators, capturing the effects of non-Clifford gates as rotations in a basis determined by the Clifford gates. This abstracts away any redundant information in the Clifford gates entirely, and can be used to merge non-Clifford gates that cannot be brought together from any sequence of commutations, as well as finding efficient Clifford constructions for the basis changes.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.passes import PauliSimp
    from pytket.utils import Graph

    circ = Circuit(3)
    circ.Rz(0.2, 0)
    circ.Rx(0.35, 1)
    circ.V(0).H(1).CX(0, 1).CX(1, 2).Rz(-0.6, 2).CX(1, 2).CX(0, 1).Vdg(0).H(1)
    circ.H(1).H(2).CX(0, 1).CX(1, 2).Rz(0.8, 2).CX(1, 2).CX(0, 1).H(1).H(2)
    circ.Rx(0.1, 1)

    PauliSimp().apply(circ)
    Graph(circ).get_DAG()

.. May not always improve the circuit if it doesn't match the structures it was designed to exploit, and the large structural changes from resynthesis could make routing harder

This can give great benefits for :py:class:`Circuit` s where non-Clifford gates are sparse and there is hence a lot of redundancy in the Clifford change-of-basis sections. But if the :py:class:`Circuit` already has a very efficient usage of Clifford gates, this will be lost when converting to the abstract representation, and so the resynthesis is likely to give less efficient sequences. The large structural changes from abstraction and resynthesis can also make routing harder to perform as the interaction graph of the logical qubits can drastically change. The effectiveness of such optimisations depends on the situation, but can be transformative under the right circumstances.

Some of these optimisation passes have optional parameters to customise the routine slightly. A good example is adapting the :py:class:`PauliSimp` pass to have a preference for different forms of ``OpType.CX`` decompositions. Setting the ``cx_config`` option to ``CXConfigType.Snake`` (default) will prefer chains of gates where the target of one becomes the control of the next, whereas ``CXConfigType.Star`` prefers using a single qubit as the control for many gates, and ``CXConfigType.Tree`` introduces entanglement in a balanced tree form. Each of these has its own benefits and drawbacks that could make it more effective for a particular routine, like ``CXConfigType.Snake`` giving circuits that are easier to route on linear nearest-neighbour architectures, ``CXConfigType.Star`` allowing any of the gates to commute through to cancel out with others at the start or end of the sequence, and ``CXConfigType.Tree`` giving optimal depth on a fully-connected device.

.. jupyter-execute::

    from pytket.circuit import Circuit, PauliExpBox
    from pytket.passes import PauliSimp
    from pytket.pauli import Pauli
    from pytket.transform import CXConfigType
    from pytket.utils import Graph

    circ = Circuit(8)
    circ.add_gate(PauliExpBox([Pauli.X, Pauli.Y, Pauli.X, Pauli.Z, Pauli.Y, Pauli.X, Pauli.Z, Pauli.Z], 0.42), [0, 1, 2, 3, 4, 5, 6, 7])

    PauliSimp(cx_config=CXConfigType.Snake).apply(circ)
    print(circ.get_commands())
    Graph(circ).get_qubit_graph()

.. jupyter-execute::

    PauliSimp(cx_config=CXConfigType.Star).apply(circ)
    print(circ.get_commands())
    Graph(circ).get_qubit_graph()

.. jupyter-execute::

    PauliSimp(cx_config=CXConfigType.Tree).apply(circ)
    print(circ.get_commands())
    Graph(circ).get_qubit_graph()

Combinators
-----------

.. Passes are building blocks that can be composed into more sophisticated strategies encapsulating the full compilation flow
.. Basic sequencing

The passes encountered so far represent elementary, self-contained transformations on :py:class:`Circuit` s. In practice, we will almost always want to apply sequences of these to combine optimisations with solving for many constraints. The passes in ``pytket`` have a rudimentary compositional structure to describe generic compilation strategies, with the most basic example being just applying a list of passes in order.

.. jupyter-execute::

    from pytket import Circuit, OpType
    from pytket.passes import auto_rebase_pass, EulerAngleReduction, SequencePass

    rebase_quil = auto_rebase_pass({OpType.CZ, OpType.Rz, OpType.Rx})
    circ = Circuit(3)
    circ.CX(0, 1).Rx(0.3, 1).CX(2, 1).Rz(0.8, 1)
    comp = SequencePass([rebase_quil, EulerAngleReduction(OpType.Rz, OpType.Rx)])
    comp.apply(circ)
    print(circ.get_commands())

.. Repeat passes until no further change - useful when one pass can enable further matches for another type of optimisation

When composing optimisation passes, we may find that applying one type of optimisation could open up opportunities for others by, for example, rearranging gates to match the desired template. To make the most of this, it may be beneficial to apply some pass combination repeatedly until no further changes are made, i.e. until we have found and exploited every simplification that we can.

.. jupyter-execute::

    from pytket import Circuit
    from pytket.passes import RemoveRedundancies, CommuteThroughMultis, RepeatPass, SequencePass

    circ = Circuit(4)
    circ.CX(2, 3).CY(1, 2).CX(0, 1).Rz(0.24, 0).CX(0, 1).Rz(0.89, 1).CY(1, 2).Rz(-0.3, 2).CX(2, 3)
    comp = RepeatPass(SequencePass([CommuteThroughMultis(), RemoveRedundancies()]))
    comp.apply(circ)
    print(circ.get_commands())

.. warning:: This looping mechanism does not directly compare the :py:class:`Circuit` to its old state from the previous iteration, instead checking if any of the passes within the loop body claimed they performed any rewrite. Some sequences of passes will do and undo some changes to the :py:class:`Circuit`, giving no net effect but nonetheless causing the loop to repeat. This can lead to infinite loops if used in such a way. Some passes where the :py:class:`Circuit` is converted to another form and back again (e.g. :py:class:`PauliSimp`) will always report that a change took place. We recommend testing any looping passes thoroughly to check for termination.

.. Repeat with metric - useful when hard to tell when a change is being made or you only care about specific changes

Increased termination safety can be given by only repeating whilst some easy-to-check metric (such as number of gates or depth) decreases. For example, we may want to try to minimise the number of ``OpType.CX`` gates since these will tend to be very slow and noisy on a lot of devices.

.. jupyter-execute::

    from pytket import Circuit, OpType
    from pytket.passes import RemoveRedundancies, CommuteThroughMultis, RepeatWithMetricPass, SequencePass

    circ = Circuit(4)
    circ.CX(2, 3).CY(1, 2).CX(0, 1).Rz(0.24, 0).CX(0, 1).Rz(0.89, 1).CY(1, 2).Rz(-0.3, 2).CX(2, 3)
    cost = lambda c : c.n_gates_of_type(OpType.CX)
    comp = RepeatWithMetricPass(SequencePass([CommuteThroughMultis(), RemoveRedundancies()]), cost)
    comp.apply(circ)  # Stops earlier than before, since removing CYs doesn't change the number of CXs
    print(circ.get_commands())

.. May reject compositions if pre/post-conditions don't match up; some passes will fail to complete or fail to achieve their objective if a circuit does not match their pre-conditions, so we prevent compositions where the latter's pre-conditions cannot be guaranteed

We mentioned earlier that each pass has a set of pre-conditions and post-conditions expressed via :py:class:`Predicate` s. We may find that applying one pass invalidates the pre-conditions of a later pass, meaning it may hit an error when applied to a :py:class:`Circuit`. For example, the :py:class:`KAKDecomposition` optimisation method can only operate on :py:class:`Circuit` s with a specific gate set which doesn't allow for any gates on more than 2 qubits, so when :py:class:`RoutingPass` can introduce ``OpType.BRIDGE`` gates over 3 qubits, this could cause an error when trying to apply :py:class:`KAKDecomposition`. When using combinators like :py:class:`SequencePass` and :py:class:`RepeatPass`, ``pytket`` checks that the passes are safe to compose, in the sense that former passes do not invalidate pre-conditions of the latter passes. This procedure uses a basic form of Hoare logic to identify new pre- and post-conditions for the combined pass and identify whether it is still satisfiable.

.. Warning about composing with `DecomposeBoxes`

A special mention here goes to the :py:class:`DecomposeBoxes` pass. Because the Box structures could potentially contain arbitrary sequences of gates, there is no guarantee that expanding them will yield a :py:class:`Circuit` that satisfies `any` :py:class:`Predicate`. Since it has potential to invalidate the pre-conditions of any subsequent pass, composing it with anything else `will` generate such an error.

.. jupyter-execute::
    :raises: RuntimeError

    from pytket.passes import DecomposeBoxes, PauliSimp, SequencePass
    # PauliSimp requires a specific gateset and no conditional gates
    # or mid-circuit measurement, so this will raise an exception
    comp = SequencePass([DecomposeBoxes(), PauliSimp()])

Predefined Sequences
---------------------

Knowing what sequences of compiler passes to apply for maximal performance is often a very hard problem and can require a lot of experimentation and intuition to predict reliably. Fortunately, there are often common patterns that are applicable to virtually any scenario, for which ``pytket`` provides some predefined sequences.

.. `FullPeepholeOptimise` kitchen-sink, but assumes a universal quantum computer

In practice, peephole and structure-preserving optimisations are almost always strictly beneficial to apply, or at least will never increase the size of the :py:class:`Circuit`. The :py:class:`FullPeepholeOptimise` pass applies Clifford simplifications, commutes single-qubit gates to the front of the circuit and applies passes to squash subcircuits of up to three qubits. This provides a one-size-approximately-fits-all "kitchen sink" solution to :py:class:`Circuit` optimisation. This assumes no device constraints by default, so will not generally preserve gateset, connectivity, etc.

When targeting a heterogeneous device architecture, solving this constraint in its entirety will generally require both placement and subsequent routing. :py:class:`DefaultMappingPass` simply combines these to apply the :py:class:`GraphPlacement` strategy and solve any remaining invalid multi-qubit operations. This is taken a step further with :py:class:`CXMappingPass` which also decomposes the introduced ``OpType.SWAP`` and ``OpType.BRIDGE`` gates into elementary ``OpType.CX`` gates.

.. `Synthesise<>` passes combine light optimisations that preserve qubit connectivity and target a specific gate set

After solving for the device connectivity, we then need to restrict what optimisations we can apply to those that won't invalidate this. The set of :py:class:`SynthesiseX` passes combine light optimisations that preserve the qubit connectivity and target a specific final gate set (e.g. :py:class:`SynthesiseTket` guarantees the output is in the gateset of ``OpType.CX``, ``OpType.TK1``, and ``OpType.Measure``). In general, this will not reduce the size of a :py:class:`Circuit` as much as :py:class:`FullPeepholeOptimise`, but has the benefit of removing some redundancies introduced by routing without invalidating it.

.. jupyter-input::

    from pytket import Circuit, OpType
    from pytket.extensions.qiskit import IBMQBackend
    from pytket.passes import FullPeepholeOptimise, DefaultMappingPass, SynthesiseTket, RebaseTket

    circ = Circuit(5)
    circ.CX(0, 1).CX(0, 2).CX(0, 3)
    circ.CZ(0, 1).CZ(0, 2).CZ(0, 3)
    circ.CX(3, 4).CX(0, 3).CX(4, 0)

    RebaseTket().apply(circ)     # Get number of 2qb gates by converting all to CX
    print(circ.n_gates_of_type(OpType.CX))

    FullPeepholeOptimise().apply(circ)      # Freely rewrite circuit
    print(circ.n_gates_of_type(OpType.CX))

    backend = IBMQBackend("ibmq_quito")
    DefaultMappingPass(backend.backend_info.architecture).apply(circ)
    RebaseTket().apply(circ)
    print(circ.n_gates_of_type(OpType.CX))  # Routing adds gates
    print(circ.get_commands())

    SynthesiseTket().apply(circ)            # Some added gates may be redundant
    print(circ.n_gates_of_type(OpType.CX))  # But not in this case

.. jupyter-output::

    9
    6
    9
    [tk1(0, 0, 1.5) node[0];, tk1(0, 0, 1.5) node[1];, tk1(0, 0, 1.5) node[2];, tk1(0, 0, 1.5) node[3];, CX node[1], node[0];, tk1(0, 0, 0.5) node[0];, CX node[1], node[2];, CX node[1], node[3];, tk1(0, 0, 0.5) node[2];, tk1(0, 0, 0.5) node[3];, CX node[3], node[4];, CX node[1], node[3];, CX node[3], node[4];, CX node[4], node[3];, CX node[3], node[4];, CX node[3], node[1];]
    9


.. Note::
    :py:class:`FullPeepholeOptimise` takes an optional ``allow_swaps`` argument. This is a boolean flag to indicate whether :py:class:`FullPeepholeOptimise` should preserve the circuit connectivity or not. If set to ``False`` the pass will presrve circuit connectivity but the circuit will generally be less optimised than if connectivity was ignored.
    
    :py:class:`FullPeepholeOptimise` also takes an optional ``target_2qb_gate`` argument to specify whether to target the {:py:class:`OpType.TK1`, :py:class:`OpType.CX`} or {:py:class:`OpType.TK1`, :py:class:`OpType.TK2`} gateset.

.. Note::
    Prevous versions of :py:class:`FullPeepholeOptimise` did not apply the :py:class:`ThreeQubitSquash` pass. There is a :py:class:`PeepholeOptimise2Q` pass which applies the old pass sequence with the :py:class:`ThreeQubitSquash` pass excluded.

.. `Backend.default_compilation_pass` gives a recommended compiler pass to solve the backend's constraints with little or light optimisation

Also in this category of pre-defined sequences, we have the :py:meth:`Backend.default_compilation_pass()` which is run by :py:meth:`Backend.get_compiled_circuit`. These give a recommended compiler pass to solve the :py:class:`Backend` s constraints with a choice of optimisation levels.

==================  ========================================================================================================
Optimisation level  Description
==================  ========================================================================================================
0                   Just solves the constraints as simply as possible. No optimisation.
1                   Adds basic optimisations (those covered by the :py:meth:`SynthesiseX` passes) for efficient compilation.
2                   Extends to more intensive optimisations (those covered by the :py:meth:`FullPeepholeOptimise` pass).
==================  ========================================================================================================

We will now demonstrate the :py:meth:`default_compilation_pass` with the different levels of optimisation using the ``ibmq_quito`` device. 

As more intensive optimisations are applied by level 2 the pass may take a long to run for large circuits. In this case it may be preferable to apply the lighter optimisations of level 1.

.. jupyter-input::

    from pytket import Circuit, OpType
    from pytket.extensions.qiskit import IBMQBackend

    circ = Circuit(3) # Define a circuit to be compiled to the backend
    circ.CX(0, 1)
    circ.H(1)
    circ.Rx(0.42, 1)
    circ.S(1)
    circ.CX(0, 2)
    circ.CX(2, 1)
    circ.Z(2)
    circ.Y(1)
    circ.CX(0, 1)
    circ.CX(2, 0)
    circ.measure_all()

    backend = IBMQBackend("ibmq_quito") # Initialise Backend

    print("Total gate count before compilation =", circ.n_gates)
    print("CX count before compilation =",  circ.n_gates_of_type(OpType.CX))

     # Now apply the default_compilation_pass at different levels of optimisation.

    for ol in range(3):
        test_circ = circ.copy()
        backend.default_compilation_pass(optimisation_level=ol).apply(test_circ)
        assert backend.valid_circuit(test_circ)
        print("Optimisation level", ol)
        print("Gates", test_circ.n_gates)
        print("CXs", test_circ.n_gates_of_type(OpType.CX))
    
.. jupyter-output::

    Total gate count before compilation = 13
    CX count before compilation = 5
    Optimisation level 0
    Gates 22
    CXs 8
    Optimisation level 1
    Gates 12
    CXs 5
    Optimisation level 2
    Gates 6
    CXs 1

**Explanation**

We see that compiling the circuit to ``ibmq_quito`` at optimisation level 0 actually increases the gate count. This is because ``ibmq_quito`` has connectivity constraints which require additional CX gates to be added to validate the circuit.
The single-qubit gates in our circuit also need to be decomposed into the IBM gatset.

We see that compiling at optimisation level 1 manages to reduce the CX count to 5. Our connectivity constraints are satisfied without increasing the CX gate count. Single-qubit gates are also combined to reduce the overall gate count further.

Finally we see that the default pass for optimisation level 2 manages to reduce the overall gate count to just 6 with only one CX gate. This is because more intensive optimisations are applied at this level including squashing passes that enable optimal two and three-qubit circuits to be synthesised. Applying these more powerful passes comes with a runtime overhead that may be noticeable for larger circuits.

Guidance for Combining Passes
-----------------------------

.. More powerful optimisations tend to have fewer guarantees on the structure of the output, so advisable to perform before trying to satisfy device constraints

We find that the most powerful optimisation techniques (those that have the potential to reduce :py:class:`Circuit` size the most for some class of :py:class:`Circuit` s) tend to have fewer guarantees on the structure of the output, requiring a universal quantum computer with the ability to perform any gates on any qubits. It is recommended to apply these early on in compilation.

.. Solving some device constraints might invalidate others, such as routing invalidating `NoMidMeasurePredicate` and `GateSetPredicate`

The passes to solve some device constraints might invalidate others: for example, the :py:class:`RoutingPass` generally invalidates :py:class:`NoMidMeasurePredicate` and :py:class:`GateSetPredicate`. Therefore, the order in which these are solved should be chosen with care.

.. Recommended order of decompose boxes, strong optimisations, placement, routing, delay measures, rebase; could insert minor optimisations between each step to tidy up any redundancies introduced as long as they preserve solved constraints

For most standard use cases, we recommend starting with :py:class:`DecomposeBoxes` to reduce the :py:class:`Circuit` down to primitive gates, followed by strong optimisation passes like :py:class:`PauliSimp` (when appropriate for the types of :py:class:`Circuit` s being considered) and :py:class:`FullPeepholeOptimise` to eliminate a large number of redundant operations. Then start to solve some more device constraints with some choice of placement and routing strategy, followed by :py:class:`DelayMeasures` to push measurements back through any introduced ``OpType.SWAP`` or ``OpType.BRIDGE`` gates, and then finally rebase to the desired gate set. The :py:meth:`Backend.default_compilation_pass()` definitions can replace this sequence from placement onwards for simplicity. Minor optimisations could also be inserted between successive steps to tidy up any redundancies introduced, as long as they preserve the solved constraints.

Initial and Final Maps
----------------------

.. Placement, routing, and other passes can change the names of qubits; the map from logical to physical qubits can be different at the start and end of the circuit; define initial and final maps
.. Can use this to identify what placement was selected or how to interpret the final state

:py:class:`PlacementPass` modifies the set of qubits used in the :py:class:`Circuit` from the logical names used during construction to the names of the physical addresses on the :py:class:`Backend`, so the logical qubit names wiil no longer exist within the :py:class:`Circuit` by design. Knowing the map between the logical qubits and the chosen physical qubits is necessary for understanding the choice of placement, interpreting the final state from a naive simulator, identifying which physical qubits each measurement was made on for error mitigation, and appending additional gates to the logical qubits after applying the pass.

Other passes like :py:class:`RoutingPass` and :py:class:`CliffordSimp` can introduce (explicit or implicit) permutations of the logical qubits in the middle of a :py:class:`Circuit`, meaning a logical qubit may exist on a different physical qubit at the start of the :py:class:`Circuit` compared to the end.

.. Encapsulating a circuit in a `CompilationUnit` allows the initial and final maps to be tracked when a pass is applied

We can wrap up a :py:class:`Circuit` in a :py:class:`CompilationUnit` to allow us to track any changes to the locations of the logical qubits when passes are applied. The :py:attr:`CompilationUnit.initial_map` is a dictionary mapping the original :py:class:`UnitID` s to the corresponding :py:class:`UnitID` used in :py:attr:`CompilationUnit.circuit`, and similarly :py:attr:`CompilationUnit.final_map` for outputs. Applying :py:meth:`BasePass.apply()` to a :py:class:`CompilationUnit` will apply the transformation to the underlying :py:class:`Circuit` and track the changes to the initial and final maps.

.. jupyter-input::

    from pytket import Circuit
    from pytket.extensions.qiskit import IBMQBackend
    from pytket.passes import DefaultMappingPass
    from pytket.predicates import CompilationUnit

    circ = Circuit(5, 5)
    circ.CX(0, 1).CX(0, 2).CX(0, 3).CX(0, 4).measure_all()
    backend = IBMQBackend("ibmq_quito")
    cu = CompilationUnit(circ)
    DefaultMappingPass(backend.backend_info.architecture).apply(cu)
    print(cu.circuit.get_commands())
    print(cu.initial_map)
    print(cu.final_map)

.. jupyter-output::

    [CX node[1], node[0];, Measure node[0] --> c[1];, CX node[1], node[2];, Measure node[2] --> c[2];, CX node[1], node[3];, Measure node[3] --> c[3];, SWAP node[1], node[3];, CX node[3], node[4];, Measure node[3] --> c[0];, Measure node[4] --> c[4];]
    {c[0]: c[0], c[1]: c[1], c[2]: c[2], c[3]: c[3], c[4]: c[4], q[0]: node[1], q[1]: node[0], q[2]: node[2], q[3]: node[3], q[4]: node[4]}
    {c[0]: c[0], c[1]: c[1], c[2]: c[2], c[3]: c[3], c[4]: c[4], q[0]: node[3], q[1]: node[0], q[2]: node[2], q[3]: node[1], q[4]: node[4]}

.. note:: No passes currently rename or swap classical data, but the classical bits are included in these maps for completeness.

Advanced Compilation Topics
---------------------------

Compiling Symbolic Circuits
===========================

.. Defining a single symbolic circuit and instantiating it multiple times saves effort in circuit construction, and means the circuit only has to be compiled once, saving time or allowing more expensive optimisations to be considered

For variational algorithms, the prominent benefit of defining a :py:class:`Circuit` symbolically and only instantiating it with concrete values when needed is that the compilation procedure would only need to be performed once. By saving time here we can cut down the overall time for an experiment; we could invest the time saved into applying more expensive optimisations on the :py:class:`Circuit` to reduce the impact of noise further.

.. Example with variational optimisation using statevector simulator

.. jupyter-execute::

    from pytket import Circuit, Qubit
    from pytket.extensions.qiskit import AerStateBackend
    from pytket.pauli import Pauli, QubitPauliString
    from pytket.utils.operators import QubitPauliOperator
    from sympy import symbols

    a, b = symbols("a b")
    circ = Circuit(2)
    circ.Ry(a, 0)
    circ.Ry(a, 1)
    circ.CX(0, 1)
    circ.Rz(b, 1)
    circ.CX(0, 1)
    xx = QubitPauliString({Qubit(0):Pauli.X, Qubit(1):Pauli.X})
    op = QubitPauliOperator({xx : 1.5})

    backend = AerStateBackend()

    # Compile once outside of the objective function
    circ = backend.get_compiled_circuit(circ)  

    def objective(params):
        state = circ.copy()
        state.symbol_substitution({a : params[0], b : params[1]})
        handle = backend.process_circuit(state) # No need to compile again
        vec = backend.get_result(handle).get_state()
        return op.state_expectation(vec)

    print(objective([0.25, 0.5]))
    print(objective([0.5, 0]))

.. Warning about `NoSymbolsPredicate` and necessity of instantiation before running on backends

.. note:: Every :py:class:`Backend` requires :py:class:`NoSymbolsPredicate`, so it is necessary to instantiate all symbols before running a :py:class:`Circuit`.

User-defined Passes
===================

We have already seen that pytket allows users to combine passes in a desired order using :py:class:`SequencePass`. An addtional feature is the :py:class:`CustomPass` which allows users to define their own custom circuit transformation using pytket.
The :py:class:`CustomPass` class accepts a ``transform`` parameter, a python function that takes a :py:class:`Circuit` as input and returns a :py:class:`Circuit` as output. 

We will show how to use :py:class:`CustomPass` by defining a simple transformation that replaces any Pauli Z gate in the :py:class:`Circuit` with a Hadamard gate, Pauli X gate, Hadamard gate chain.

.. jupyter-execute::

    from pytket import Circuit, OpType
    
    def z_transform(circ: Circuit) -> Circuit:
        n_qubits = circ.n_qubits
        circ_prime = Circuit(n_qubits) # Define a replacement circuit

        for cmd in circ.get_commands():
            qubit_list = cmd.qubits # Qubit(s) our gate is applied on (as a list)
            if cmd.op.type == OpType.Z:
                # If cmd is a Z gate, decompose to a H, X, H sequence.
                circ_prime.add_gate(OpType.H, qubit_list)
                circ_prime.add_gate(OpType.X, qubit_list)
                circ_prime.add_gate(OpType.H, qubit_list)
            else: 
                # Otherwise, apply the gate as usual.
                circ_prime.add_gate(cmd.op.type, cmd.op.params, qubit_list)

        return circ_prime

After we've defined our ``transform`` we can construct a :py:class:`CustomPass`. This pass can then be applied to a :py:class:`Circuit`.

.. jupyter-execute::

    from pytket.passes import CustomPass

    DecompseZPass = CustomPass(z_transform) # Define our pass

    test_circ = Circuit(2) # Define a test Circuit for our pass
    test_circ.Z(0)
    test_circ.Z(1)
    test_circ.CX(0, 1)
    test_circ.Z(1)
    test_circ.CRy(0.5, 0, 1)
    
    DecompseZPass.apply(test_circ) # Apply our pass to the test Circuit

    test_circ.get_commands() # Commands of our transformed Circuit

We see from the output above that our newly defined :py:class:`DecompseZPass` has successfully decomposed the Pauli Z gates to Hadamard, Pauli X, Hadamard chains and left other gates unchanged.

.. warning::
    pytket does not require that :py:class:`CustomPass` preserves the unitary of the :py:class:`Circuit` . This is for the user to ensure.


Partial Compilation
===================

.. Commonly want to run many circuits that have large identical regions; by splitting circuits into regions, can often compile individually and compose to speed up compilation time

A common pattern across expectation value and tomography experiments is to run many :py:class:`Circuit` s that have large identical regions, such as a single state preparation with many different measurements. We can further speed up the overall compilation time by splitting up the state preparation from the measurements, compiling each subcircuit only once, and composing together at the end.

.. Only have freedom to identify good placements for the first subcircuit to be run, the rest are determined by final maps in order to compose well

The main technical consideration here is that the compiler will only have the freedom to identify good placements for the first subcircuit to be run. This means that the state preparation should be compiled first, and the placement for the measurements is given by the final map in order to compose well.

Once compiled, we can use :py:meth:`Backend.process_circuits` to submit several circuits at once for execution on the backend. The circuits to be executed are passed as list. If the backend is shot-based, the number of shots can be passed using the `n_shots` parameter, which can be a single integer or a list of integers of the same length as the list of circuits to be executed. In the following example, 4000 shots are measured for the first circuit and 2000 for the second.

.. Example of state prep with many measurements; compile state prep once, inspect final map, use this as placement for measurement circuits and compile them, then compose

.. jupyter-input::

    from pytket import Circuit, OpType
    from pytket.extensions.qiskit import IBMQBackend
    from pytket.predicates import CompilationUnit
    from pytket.placement import Placement

    state_prep = Circuit(4)
    state_prep.H(0)
    state_prep.add_gate(OpType.CnRy, 0.1, [0, 1])
    state_prep.add_gate(OpType.CnRy, 0.2, [0, 2])
    state_prep.add_gate(OpType.CnRy, 0.3, [0, 3])

    measure0 = Circuit(4, 4)
    measure0.H(1).H(3).measure_all()
    measure1 = Circuit(4, 4)
    measure1.CX(1, 2).CX(3, 2).measure_all()

    backend = IBMQBackend("ibmq_quito")
    cu = CompilationUnit(state_prep)
    backend.default_compilation_pass().apply(cu)
    Placement.place_with_map(measure0, cu.final_map)
    Placement.place_with_map(measure1, cu.final_map)
    backend.default_compilation_pass().apply(measure0)
    backend.default_compilation_pass().apply(measure1)

    circ0 = cu.circuit
    circ1 = circ0.copy()
    circ0.append(measure0)
    circ1.append(measure1)
    handles = backend.process_circuits([circ0, circ1], n_shots=[4000, 2000])
    r0, r1 = backend.get_results(handles)
    print(r0.get_counts())
    print(r1.get_counts())

.. jupyter-output::

    {(0, 0, 0, 0): 503, (0, 0, 0, 1): 488, (0, 1, 0, 0): 533, (0, 1, 0, 1): 493, (1, 0, 0, 0): 1041, (1, 0, 0, 1): 107, (1, 0, 1, 0): 115, (1, 0, 1, 1): 14, (1, 1, 0, 0): 576, (1, 1, 0, 1): 69, (1, 1, 1, 0): 54, (1, 1, 1, 1): 7}
    {(0, 0, 0, 0): 2047, (0, 1, 0, 0): 169, (0, 1, 1, 0): 1729, (1, 1, 0, 0): 7, (1, 1, 1, 0): 48}

Measurement Reduction
=====================

.. Measurement scenario has a single state generation circuit but many measurements we want to make; suppose each measurements is Pauli
.. Naively, need one measurement circuit per measurement term
.. Commuting observables can be measured simultaneously

Suppose we have one of these measurement scenarios (i.e. a single state preparation, but many measurements to make on it) and that each of the measurements is a Pauli observable, such as when calculating the expectation value of the state with respect to some :py:class:`QubitPauliOperator`. Naively, we would need a different measurement :py:class:`Circuit` per term in the operator, but we can reduce this by exploiting the fact that commuting observables can be measured simultaneously.

.. Given a set of observables, partition into sets that are easy to measure simultaneously and generate circuits performing this by diagonalising them (reducing each to a combination of Z-measurements)

Given a set of observables, we can partition them into subsets that are easy to measure simultaneously. A :py:class:`Circuit` is generated for each subset by diagonalising the observables (reducing all of them to a combination of :math:`Z`-measurements).

.. Commuting sets vs non-conflicting sets

Diagonalising a mutually commuting set of Pauli observables could require an arbitrary Clifford circuit in general. If we are considering the near-term regime where "every gate counts", the diagonalisation of the observables could introduce more of the (relatively) expensive two-qubit gates, giving us the speedup at the cost of some extra noise. ``pytket`` can partition the Pauli observables into either general commuting sets for improved reduction in the number of measurement :py:class:`Circuit` s, or into smaller sets which can be diagonalised without introducing any multi-qubit gates - this is possible when all observables are substrings of some measured Pauli string (e.g. `XYI` and `IYZ` is fine, but `ZZZ` and `XZX` is not).

.. Could have multiple circuits producing the same observable, so can get extra shots/precision for free

This measurement partitioning is built into the :py:meth:`get_operator_expectation_value` utility method, or can be used directly using :py:meth:`pytket.partition.measurement_reduction()` which builds a :py:class:`MeasurementSetup` object. A :py:class:`MeasurementSetup` contains a list of measurement :py:class:`Circuit` s and a map from the :py:class:`QubitPauliString` of each observable to the information required to extract the expectation value (which bits to consider from which :py:class:`Circuit`).

.. jupyter-execute::

    from pytket import Qubit
    from pytket.pauli import Pauli, QubitPauliString
    from pytket.partition import measurement_reduction, PauliPartitionStrat

    zi = QubitPauliString({Qubit(0):Pauli.Z})
    iz = QubitPauliString({Qubit(1):Pauli.Z})
    zz = QubitPauliString({Qubit(0):Pauli.Z, Qubit(1):Pauli.Z})
    xx = QubitPauliString({Qubit(0):Pauli.X, Qubit(1):Pauli.X})
    yy = QubitPauliString({Qubit(0):Pauli.Y, Qubit(1):Pauli.Y})

    setup = measurement_reduction([zi, iz, zz, xx, yy], strat=PauliPartitionStrat.CommutingSets)
    print("Via Commuting Sets:")
    for i, c in enumerate(setup.measurement_circs):
        print(i, c.get_commands())
    print(setup.results[yy])

    setup = measurement_reduction([zi, iz, zz, xx, yy], strat=PauliPartitionStrat.NonConflictingSets)
    print("Via Non-Conflicting Sets:")
    for i, c in enumerate(setup.measurement_circs):
        print(i, c.get_commands())
    print(setup.results[yy])

.. note:: Since there could be multiple measurement :py:class:`Circuit` s generating the same observable, we could theoretically use this to extract extra shots (and hence extra precision) for that observable for free; automatically doing this as part of :py:meth:`measurement_reduction()` is planned for a future release of ``pytket``.

Contextual Optimisations
========================

By default, tket makes no assumptions about a circuit's input state, nor about
the destiny of its output state. We can therefore compose circuits freely,
construct boxes from them that we can then place inside other circuits, and so
on. However, when we come to run a circuit on a real device we can almost always
assume that it will be initialised in the all-zero state, and that the final
state of the qubits will be discarded (after measurement).

This is where `contextual optimisations` can come into play. These are
optimisations that depend on knowledge of the context of the circuit being run.
They do not generally preserve the full unitary, but they generate circuits that
are observationally indistinguishable (on an ideal device), and reduce noise by
eliminating unnecessary operations from the beginning or end of the circuit.

First of all, tket provides methods to `annotate` a qubit (or all qubits) as
being initialized to zero, or discarded at the end of the circuit, or both.

.. jupyter-execute::

    from pytket import Circuit

    c = Circuit(2)
    c.Y(0)
    c.CX(0,1)
    c.H(0)
    c.H(1)
    c.Rz(0.125, 1)
    c.measure_all()
    c.qubit_create_all()
    c.qubit_discard_all()

The last two lines tell the compiler that all qubits are to be initialized to
zero and discarded at the end. The methods :py:meth:`Circuit.qubit_create` and
:py:meth:`Circuit.qubit_discard` can be used to achieve the same on individual
qubits.

.. warning:: Note that we are now restricted in how we can compose our circuit with other circuits. When composing after another circuit, a "created" qubit becomes a Reset operation. Whem composing before another circuit, a "discarded" qubit may not be joined to another qubit unless that qubit has itself been "created" (so that the discarded state gets reset to zero).

Initial simplification
~~~~~~~~~~~~~~~~~~~~~~

When the above circuit is run from an all-zero state, the Y and CX gates at the
beginning just have the effect of putting both qubits in the :math:`\lvert 1
\rangle` state (ignoring unobservable global phase), so they could be replaced
with two X gates. This is exactly what the :py:meth:`SimplifyInitial` pass does.

.. jupyter-execute::

    from pytket.passes import SimplifyInitial

    SimplifyInitial().apply(c)
    print(c.get_commands())

This pass tracks the state of qubits known to be initialised to zero (or reset
mid-circuit) forward through the circuit, for as long as the qubits remain in a
computational basis state, either removing gates (when they don't change the
state) or replacing them with X gates (when they invert the state).

By default, this pass also replaces Measure operations acting on qubits with a
known state by classical set-bits operations on the target bits:

.. jupyter-execute::

    c = Circuit(1).X(0).measure_all()
    c.qubit_create_all()
    SimplifyInitial().apply(c)
    print(c.get_commands())

The measurement has disappeared, replaced with a classical operation on its
target bit. To disable this behaviour, pass the ``allow_classical=False``
argument to :py:meth:`SimplifyInitial` when constructing the pass.

.. warning:: Most backends currently do not support set-bit operations, so these could cause errors when using this pass with mid-circuit measurements. In such cases you should set ``allow_classical=False``.

Note that :py:meth:`SimplifyInitial` does not automatically cancel successive
pairs of X gates introduced by the simplification. It is a good idea to follow
it with a :py:meth:`RemoveRedundancies` pass in order to perform these
cancellations.

Removal of discarded operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An operation that has no quantum or classical output in its causal future has no
effect (or rather, no observable effect on an ideal system), and can be removed
from the circuit. By marking a qubit as discarded, we tell the compiler that it
has no quantum output, potentially enabling this simplification.

Note that if the qubit is measured, even if it is then discarded, the Measure
operation has a classical output in its causal future so will not be removed.

.. jupyter-execute::

    from pytket.circuit import Qubit
    from pytket.passes import RemoveDiscarded

    c = Circuit(3, 2)
    c.H(0).H(1).H(2).CX(0, 1).Measure(0, 0).Measure(1, 1).H(0).H(1)
    c.qubit_discard(Qubit(0))
    c.qubit_discard(Qubit(2))
    RemoveDiscarded().apply(c)
    print(c.get_commands())

The Hadamard gate following the measurement on qubit 0, as well as the Hadamard
on qubit 2, have disappeared, because those qubits were discarded. The Hadamard
following the measurement on qubit 1 remains, because that qubit was not
discarded.

Commutation of measured classical maps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The last type of contextual optimization is a little more subtle. Let's call a
quantum unitary operation a `classical map` if it sends every computational
basis state to a computational basis state, possibly composed with a diagonal
operator. For example, X, Y, Z, Rz, CX, CY, CZ and Sycamore are classical maps,
but Rx, Ry and H are not. Check the
`documentation of gate types <https://tket.quantinuum.com/api-docs/optype.html>`_
to see which gates have unitaries that make them amenable to optimisation.

When a classical map is followed by a measurement of all its qubits, and those
qubits are then discarded, it can be replaced by a purely classical operation
acting on the classical outputs of the measurement.

For example, if we apply a CX gate and then measure the two qubits, the result
is (ideally) the same as if we measured the two qubits first and then applied a
classical controlled-NOT on the measurement bits. If the gate were a CY instead
of a CX the effect would be identical: the only difference is the insertion of a
diagonal operator, whose effect is unmeasurable.

This simplification is effected by the :py:meth:`SimplifyMeasured` pass.

Let's illustrate this with a Bell circuit:

.. jupyter-execute::

    from pytket.passes import SimplifyMeasured

    c = Circuit(2).H(0).CX(0, 1).measure_all()
    c.qubit_discard_all()
    SimplifyMeasured().apply(c)
    print(c.get_commands())

The CX gate has disappeared, replaced with a classical transform acting on the
bits after the measurement.

Contextual optimisation in practice
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The above three passes are combined in the :py:meth:`ContextSimp` pass, which
also performs a final :py:meth:`RemoveRedundancies`. Normally, before running a
circuit on a device you will want to apply this pass (after using
:py:meth:`Circuit.qubit_create_all` and :py:meth:`Circuit.qubit_discard_all` to
enable the simplifications).

However, most backends cannot process the classical operations that may be
introduced by :py:meth:`SimplifyMeasured` or (possibly)
:py:meth:`SimplifyInitial`. So pytket provides a method
:py:meth:`separate_classical` to separate the classical postprocessing circuit
from the main circuit to be run on the device. This postprocessing circuit is
then passed as the ``ppcirc`` argument to :py:meth:`BackendResult.get_counts` or
:py:meth:`BackendResult.get_shots`, in order to obtain the postprocessed
results.

Much of the above is wrapped up in the utility method
:py:meth:`prepare_circuit`. This takes a circuit, applies
:py:meth:`Circuit.qubit_create_all` and :py:meth:`Circuit.qubit_discard_all`,
runs the full :py:meth:`ContextSimp` pass, and then separates the result into
the main circuit and the postprocessing circuit, returning both.

Thus a typical usage would look something like this:

.. jupyter-execute::

    from pytket.utils import prepare_circuit
    from pytket.extensions.qiskit import AerBackend

    b = AerBackend()
    c = Circuit(2).H(0).CX(0, 1)
    c.measure_all()
    c0, ppcirc = prepare_circuit(c)
    c0 = b.get_compiled_circuit(c0)
    h = b.process_circuit(c0, n_shots=10)
    r = b.get_result(h)
    shots = r.get_shots(ppcirc=ppcirc)
    print(shots)

This is a toy example, but illustrates the principle. The actual circuit sent to
the backend consisted only of a Hadamard gate on qubit 0 and a single
measurement to bit 0. The classical postprocessing circuit set bit 1 to zero and
then executed a controlled-NOT from bit 0 to bit 1. These details are hidden
from us (unless we inspect the circuits), and what we end up with is a shots
table that is indistinguishable from running the original circuit but with less
noise.
