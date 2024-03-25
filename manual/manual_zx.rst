***********
ZX Diagrams
***********

Aside from optimisation methods focussed on localised sequences of gates, the ZX-calculus has shown itself to be a useful representation for quantum operations that can highlight and exploit some specific kinds of higher-level redundancy in the structure of the circuit. In this section, we will assume the reader is familiar with the theory of ZX-calculus in terms of how to construct diagrams, apply rewrites to them, and interpret them as linear maps. We will focus on how to make use of the ZX module in ``pytket`` to help automate and scale your ideas. For a comprehensive introduction to the theory, we recommend reading van de Wetering's overview paper [vdWet2020]_ or taking a look at the resources available at `zxcalculus.com <https://zxcalculus.com>`_.

The graph representation used in the ZX module is intended to be sufficiently generalised to support experimentation with other graphical calculi like ZH, algebraic ZX, and MBQC patterns. This includes:

* Port annotations on edges to differentiate between multiple incident edges on a vertex for asymmetric generators such as subdiagram abstractions (:py:class:`ZXBox`) or the triangle generator of algebraic ZX.

* Structured generators for varied parameterisations, such as continuous real parameters of ZX spiders and discrete (Boolean) parameters of specialised Clifford generators.

* Mixed quantum-classical diagram support via annotating edges and some generators with :py:class:`QuantumType.Quantum` for doubled diagrams (shorthand notation for a pair of adjoint edges/generators) or :py:class:`QuantumType.Classical` for the singular variants (sometimes referred to as decoherent/bastard generators).

.. note:: Providing this flexibility comes at the expense of some efficiency in both memory and speed of operations. For data structures more focussed on the core ZX-calculus and its well-developed simplification strategies, we recommend checking out ``pyzx`` (https://github.com/Quantomatic/pyzx) and its Rust port ``quizx`` (https://github.com/Quantomatic/quizx). Some functionality for interoperation between ``pytket`` and ``pyzx`` circuits is provided in the ``pytket-pyzx`` extension package. There is no intention to support non-qubit calculi or SZX scalable notation in the near future as the additional complexity required by the data structure would introduce excessive bureaucracy to maintain during every rewrite.

Generator Types
---------------

Before we start building diagrams, it is useful to cover the kinds of generators we can populate them with. A full list and details can be found in the API reference.

* Boundary generators: :py:class:`ZXType.Input`, :py:class:`ZXType.Output`, :py:class:`ZXType.Open`. These are used to turn some edges of the diagram into half-edges, indicating the input, output, or unspecified boundaries of the diagram. These will be maintained in an ordered list in a :py:class:`ZXDiagram` to specify the intended order of indices when interpreting the diagram as a tensor.

* Symmetric ZXH generators: :py:class:`ZXType.ZSpider`, :py:class:`ZXType.XSpider`, :py:class:`ZXType.HBox`. These are the familiar generators from standard literature. All incident edges are exchangeable, so no port information is used (all edges attach at port ``None``). The degenerate :py:class:`QuantumType.Classical` variants support both :py:class:`QuantumType.Classical` and :py:class:`QuantumType.Quantum` incident edges, with the latter being treated as two distinct edges.

* MBQC generators: :py:class:`ZXType.XY`, :py:class:`ZXType.XZ`, :py:class:`ZXType.YZ`, :py:class:`ZXType.PX`, :py:class:`ZXType.PY`, :py:class:`ZXType.PZ`. These represent qubits in a measurement pattern that are postselected into the correct outcome (i.e. we do not consider errors and corrections as these can be inferred by flow detection). Each of them can be thought of as shorthand for a :py:class:`ZXType.ZSpider` with an adjacent spider indicating the postselection projector. The different types indicate either planar measurements with a continuous-parameter angle or a Pauli measurement with a Boolean angle selecting which outcome is the intended. Entanglement between qubits can be established with a :py:class:`ZXWireType.H` edge between vertices, with :py:class:`ZXWireType.Basic` edges connecting to a :py:class:`ZXType.Input` to indicate input qubits. Unmeasured output qubits can be indicated using a :py:class:`ZXType.PX` vertex (essentially a zero phase :py:class:`ZXType.ZSpider`) attached to a :py:class:`ZXType.Output`.

* :py:class:`ZXType.ZXBox`. Similar to the concept of a :py:class:`~pytket.circuit.CircBox` for circuits, a :py:class:`ZXBox` contains another :py:class:`ZXDiagram` abstracted away which can later be expanded in-place. The ports and :py:class:`QuantumType` of incident edges will align with the indices and types of the boundaries on the inner diagram.

Each generator in a diagram is described by a :py:class:`ZXGen` object, or rather an object of one of its concrete subtypes depending on the data needed to describe the generator.

Creating Diagrams
-----------------

Let's start by making the standard diagram for the qubit teleportation algorithm to showcase the capacity for mixed quantum-classical diagrams. Assuming that the Bell pair will be written in as initialised ancillae rather than open inputs, we just need to start with a diagram with just one quantum input and one quantum output.

.. jupyter-execute::

    import pytket
    from pytket.zx import ZXDiagram, ZXType, QuantumType, ZXWireType
    import graphviz as gv

    tele = ZXDiagram(1, 1, 0, 0)
    gv.Source(tele.to_graphviz_str())

We will choose to represent the Bell state as a cup (i.e. an edge connecting one side of the CX to the first correction). In terms of vertices, we need two for the CX gate, two for the measurements, and four for the encoding and application of corrections. The CX and corrections need to be coherent operations so will be :py:class:`QuantumType.Quantum` as opposed to the measurements and encodings. We can then link them up by adding edges of the appropriate :py:class:`QuantumType`. The visualisations will show :py:class:`QuantumType.Quantum` generators and edges with thick lines and :py:class:`QuantumType.Classical` with thinner lines as per standard notation conventions.

.. jupyter-execute::

    (in_v, out_v) = tele.get_boundary()
    cx_c = tele.add_vertex(ZXType.ZSpider)
    cx_t = tele.add_vertex(ZXType.XSpider)
    z_meas = tele.add_vertex(ZXType.ZSpider, qtype=QuantumType.Classical)
    x_meas = tele.add_vertex(ZXType.XSpider, qtype=QuantumType.Classical)
    z_enc = tele.add_vertex(ZXType.ZSpider, qtype=QuantumType.Classical)
    x_enc = tele.add_vertex(ZXType.XSpider, qtype=QuantumType.Classical)
    z_correct = tele.add_vertex(ZXType.ZSpider)
    x_correct = tele.add_vertex(ZXType.XSpider)

    # Bell pair between CX and first correction
    tele.add_wire(cx_t, x_correct)

    # Apply CX between input and first ancilla
    tele.add_wire(in_v, cx_c)
    tele.add_wire(cx_c, cx_t)

    # Measure first two qubits
    tele.add_wire(cx_c, x_meas)
    tele.add_wire(cx_t, z_meas)

    # Feed measurement outcomes to corrections
    tele.add_wire(x_meas, x_enc, qtype=QuantumType.Classical)
    tele.add_wire(x_enc, z_correct)
    tele.add_wire(z_meas, z_enc, qtype=QuantumType.Classical)
    tele.add_wire(z_enc, x_correct)

    # Apply corrections to second ancilla
    tele.add_wire(x_correct, z_correct)
    tele.add_wire(z_correct, out_v)

    gv.Source(tele.to_graphviz_str())

We can use this teleportation algorithm as a component in a larger diagram using a :py:class:`ZXBox`. Here, we insert it in the middle of a two qubit circuit.

.. jupyter-execute::

    circ_diag = ZXDiagram(2, 1, 0, 1)
    qin0 = circ_diag.get_boundary(ZXType.Input)[0]
    qin1 = circ_diag.get_boundary(ZXType.Input)[1]
    qout = circ_diag.get_boundary(ZXType.Output)[0]
    cout = circ_diag.get_boundary(ZXType.Output)[1]

    cz_c = circ_diag.add_vertex(ZXType.ZSpider)
    cz_t = circ_diag.add_vertex(ZXType.ZSpider)
    # Phases of spiders are given in half-turns, so this is a pi/4 rotation
    rx = circ_diag.add_vertex(ZXType.XSpider, 0.25)
    x_meas = circ_diag.add_vertex(ZXType.XSpider, qtype=QuantumType.Classical)
    box = circ_diag.add_zxbox(tele)

    # CZ between inputs
    circ_diag.add_wire(qin0, cz_c)
    circ_diag.add_wire(qin1, cz_t)
    circ_diag.add_wire(cz_c, cz_t, type=ZXWireType.H)

    # Rx on first qubit
    circ_diag.add_wire(cz_c, rx)

    # Teleport first qubit
    # The inputs appear first in the boundary of tele, so port 0 is the input
    circ_diag.add_wire(u=rx, v=box, v_port=0)
    # Port 1 for the output
    circ_diag.add_wire(u=box, v=qout, u_port=1)

    # Measure second qubit destructively and output result
    circ_diag.add_wire(cz_t, x_meas)
    circ_diag.add_wire(x_meas, cout, type=ZXWireType.H, qtype=QuantumType.Classical)

    gv.Source(circ_diag.to_graphviz_str())

.. Validity conditions of a diagram

As the entire graph data structure is exposed, it is very easy to construct objects that cannot be interpreted as a valid diagram. This is to be expected from intermediate states during the construction of a diagram or in the middle of applying a rewrite, before the state is returned to something sensible. The :py:meth:`ZXDiagram.check_validity()` method will perform a number of sanity checks on a given diagram object and it will raise an exception if any of them fail. We recommend using this during debugging to check that the diagram is not left in an invalid state. A diagram is deemed valid if it satisfies each of the following:

* Any vertex with of a boundary type (:py:class:`ZXType.Input`, :py:class:`ZXType.Output`, or :py:class:`ZXType.Open`) must have degree 1 (they uniquely identify a single edge as open) and exist in the boundary list.

* Undirected vertices (those without port information, such as :py:class:`ZXType.ZSpider`, or :py:class:`ZXType.HBox`) have no port annotations on incident edges.

* Directed vertices (such as :py:class:`ZXType.Triangle` or :py:class:`ZXType.ZXBox`) have exactly one incident edge at each port.

* The :py:class:`QuantumType` of each edge is compatible with the vertices and ports they attach to. For example, a :py:class:`ZXType.ZSpider` with :py:class:`QuantumType.Quantum` requires all incident edges to also have :py:class:`QuantumType.Quantum`, whereas a :py:class:`QuantumType.Classical` vertex accepts any edge, and for a :py:class:`ZXType.ZXBox` the :py:class:`QuantumType` of an edge must match the signature at the corresponding port.

Tensor Evaluation
-----------------

Evaluating a diagram as a tensor is beneficial for practical use cases in scalar diagram evaluation (e.g. as part of expectation value calculations or simulation tasks), or for verification of correctness of diagram designs or rewrites. Evaluation is performed by building a tensor network out of the definitions of the generators and using a contraction strategy to reduce it down to a single tensor. Each diagram carries a global scalar which is multiplied into the tensor.

.. Mixed diagrams and different evaluation methods (global phase/scalar); reasons to use Quantum or Classical

As the pytket ZX diagrams represent mixed diagrams, this impacts the interpretation of the tensors. Traditionally, we expect each edge of a ZX diagram to have dimension 2. This is the case for :py:class:`QuantumType.Classical` edges, but since :py:class:`QuantumType.Quantum` edges represent a pair via doubling, they instead have dimension 4. The convention set by density matrix notation is to split this into two different indices, so :py:meth:`tensor_from_mixed_diagram()` will first expand the doubling notation in the diagram explicitly to give a diagram with only :py:class:`QuantumType.Classical` edges and then evaluate it, meaning there will be an index for each original :py:class:`QuantumType.Quantum` edge and a new one for its conjugate. In particular, this will increase the number of boundary edges and therefore the expected rank of the overall tensor. The ordering of the indices will primarily follow the boundary order in the original diagram, subordered by doubling index for each :py:class:`QuantumType.Quantum` boundary as in the following example.

.. jupyter-execute::

    from pytket.zx.tensor_eval import tensor_from_mixed_diagram
    ten = tensor_from_mixed_diagram(circ_diag)
    # Indices are (qin0, qin0_conj, qin1, qin1_conj, qout, qout_conj, cout)
    print(ten.shape)
    print(ten[:, :, 1, 1, 0, 0, :].round(4))

In many cases, we work with pure quantum diagrams. This doubling would cause substantial blowup in time and memory for evaluation, as well as making the tensor difficult to navigate for large diagrams. :py:meth:`tensor_from_quantum_diagram()` achieves the same as converting all :py:class:`QuantumType.Quantum` components to :py:class:`QuantumType.Classical`, meaning every edge is reduced down to dimension 2. Since the global scalar is maintained with respect to a doubled diagram, its square root is incorporated into the tensor, though we do not maintain the coherent global phase of a pure quantum diagram in this way. For diagrams like this, :py:meth:`unitary_from_quantum_diagram()` reformats the tensor into the conventional unitary (with big-endian indexing).

.. jupyter-execute::

    from pytket.zx.tensor_eval import tensor_from_quantum_diagram, unitary_from_quantum_diagram
    u_diag = ZXDiagram(2, 2, 0, 0)
    ins = u_diag.get_boundary(ZXType.Input)
    outs = u_diag.get_boundary(ZXType.Output)
    cx_c = u_diag.add_vertex(ZXType.ZSpider)
    cx_t = u_diag.add_vertex(ZXType.XSpider)
    rz = u_diag.add_vertex(ZXType.ZSpider, -0.25)

    u_diag.add_wire(ins[0], cx_c)
    u_diag.add_wire(ins[1], cx_t)
    u_diag.add_wire(cx_c, cx_t)
    u_diag.add_wire(cx_t, rz)
    u_diag.add_wire(cx_c, outs[0])
    u_diag.add_wire(rz, outs[1])

    print(tensor_from_quantum_diagram(u_diag).round(4))
    print(unitary_from_quantum_diagram(u_diag).round(4))

Similarly, one may use :py:meth:`density_matrix_from_cptp_diagram()` to obtain a density matrix when all boundaries are :py:class:`QuantumType.Quantum` but the diagram itself contains mixed components. When input boundaries exist, this gives the density matrix under the Choi-Jamiołkovski isomorphism. For example, we can verify that our teleportation diagram from earlier really does reduce to the identity (recall that the Choi-Jamiołkovski isomorphism maps the identity channel to a Bell state).

.. jupyter-execute::

    from pytket.zx.tensor_eval import density_matrix_from_cptp_diagram

    print(density_matrix_from_cptp_diagram(tele))

.. Tensor indices, unitaries and states; initialisation and post-selection

Another way to potentially reduce the computational load for tensor evaluation is to fix basis states at the boundary vertices, corresponding to initialising inputs or post-selecting on outputs. There are utility methods for setting all inputs/outputs or specific boundary vertices to Z-basis states. For example, we can recover statevector simulation of a quantum circuit by setting all inputs to the zero state and calling :py:meth:`unitary_from_quantum_diagram()`.

.. jupyter-execute::

    from pytket.zx.tensor_eval import fix_inputs_to_binary_state
    state_diag = fix_inputs_to_binary_state(u_diag, [1, 0])
    print(unitary_from_quantum_diagram(state_diag).round(4))

.. Note on location in test folder

Graph Traversal, Inspection, and Manual Rewriting
-------------------------------------------------

The ability to build static diagrams is fine for visualisation and simulation needs, but the bulk of interest in graphical calculi is in rewriting for simplification. For this, it is enough to traverse the graph to search for relevant subgraphs and manipulate the graph in place. We will illustrate this by gradually rewriting the teleportation diagram to be the identity.

.. jupyter-execute::

    gv.Source(tele.to_graphviz_str())

.. Boundaries (ordering, types and incident edges, not associated to UnitIDs)

The boundary vertices offer a useful starting point for traversals. Each :py:class:`ZXDiagram` maintains an ordered list of its boundaries to help distinguish them (note that this is different from the :py:class:`UnitID` system used by :py:class:`~pytket.circuit.Circuit` objects), which we can retrieve with :py:meth:`ZXDiagram.get_boundary()`. Each boundary vertex should have a unique incident edge which we can access through :py:meth:`ZXDiagram.adj_wires()`.

.. Semi-ordered edges, incident edge order and traversal, edge properties and editing

Once we have an edge, we can inspect and modify its properties, specifically its :py:class:`QuantumType` with :py:meth:`ZXDiagram.get/set_wire_qtype()` (whether it represents a single wire or a pair of wires under the doubling construction) and :py:class:`ZXWireType` with :py:meth:`ZXDiagram.get/set_wire_type()` (whether it is equivalent to an identity process or a Hadamard gate). To change the end points of a wire (even just moving it to another port on the same vertex), it is conventional to remove it and create a new wire.

.. jupyter-execute::

    (in_v, out_v) = tele.get_boundary()
    in_edge = tele.adj_wires(in_v)[0]
    print(tele.get_wire_qtype(in_edge))
    print(tele.get_wire_type(in_edge))

The diagram is presented as an undirected graph. We can inspect the end points of an edge with :py:meth:`ZXDiagram.get_wire_ends()`, which returns pairs of vertex and port. If we simply wish to traverse the edge to the next vertex, we use :py:meth:`ZXDiagram.other_end()`. Or we can skip wire traversal altogether using :py:meth:`ZXDiagram.neighbours()` to enumerate the neighbours of a given vertex. This is mostly useful when the wires in a diagram have a consistent form, such as in a graphlike or MBQC diagram (every wire is a Hadamard except for boundary wires).

If you are searching the diagram for a pattern that is simple enough that a full traversal would be excessive, :py:class:`ZXDiagram.vertices` and :py:class:`ZXDiagram.wires` return lists of all vertices or edges in the diagram at that moment (in a deterministic but not semantically relevant order) which you can iterate over to search the graph quickly. Be aware that inserting or removing components of the diagram during iteration will not update these lists.

.. jupyter-execute::

    cx_c = tele.other_end(in_edge, in_v)
    assert tele.get_wire_ends(in_edge) == ((in_v, None), (cx_c, None))

    for v in tele.vertices:
        print(tele.get_zxtype(v))

Using this, we can scan our diagram for adjacent spiders of the same colour connected by a basic edge to apply spider fusion. In general, this will require us to also inspect the generators of the vertex to be able to add the phases and update the :py:class:`QuantumType` in case of merging with a :py:class:`QuantumType.Classical` spider.

.. Vertex contents, generators, and editing vertex

Similar to edges, each vertex contains a :py:class:`ZXGen` object describing the particular generator it represents which we can retrieve using :py:meth:`ZXDiagram.get_vertex_ZXGen()`. As each kind of generator has different data, when using a diagram with many kinds of generators it is useful to inspect the :py:class:`ZXType` or the subclass of :py:class:`ZXGen` first. For example, if :py:meth:`ZXDiagram.get_zxtype()` returns :py:class:`ZXType.ZSpider`, we know the generator is a :py:class:`PhasedGen` and hence has the :py:class:`PhasedGen.param` field describing the phase of the spider.

Each generator object is immutable, so updating a vertex requires creating a new :py:class:`ZXGen` object with the desired properties and passing it to :py:meth:`ZXDiagram.set_vertex_ZXGen()`.

.. jupyter-execute::

    from pytket.zx import PhasedGen

    def fuse():
        removed = []
        for v in tele.vertices:
            if v in removed or tele.get_zxtype(v) not in (ZXType.ZSpider, ZXType.XSpider):
                continue
            for w in tele.adj_wires(v):
                if tele.get_wire_type(w) != ZXWireType.Basic:
                    continue
                
                n = tele.other_end(w, v)
                if tele.get_zxtype(n) != tele.get_zxtype(v):
                    continue
                
                # Match found, copy n's edges onto v
                for nw in tele.adj_wires(n):
                    if nw != w:
                        # We know all vertices here are symmetric generators so we 
                        # don't need to care about port information
                        nn = tele.other_end(nw, n)
                        wtype = tele.get_wire_type(nw)
                        qtype = tele.get_wire_qtype(nw)
                        tele.add_wire(v, nn, wtype, qtype)
                # Update v to have total phase
                n_spid = tele.get_vertex_ZXGen(n)
                v_spid = tele.get_vertex_ZXGen(v)
                v_qtype = QuantumType.Classical if n_spid.qtype == QuantumType.Classical or v_spid.qtype == QuantumType.Classical else QuantumType.Quantum
                tele.set_vertex_ZXGen(v, PhasedGen(v_spid.type, v_spid.param + n_spid.param, v_qtype))
                # Remove n
                tele.remove_vertex(n)
                removed.append(n)
    
    fuse()
    
    gv.Source(tele.to_graphviz_str())

Similarly, we can scan for a pair of adjacent basic edges between a green and a red spider for the strong complementarity rule.

.. jupyter-execute::

    def strong_comp():
        gr_edges = dict()
        for w in tele.wires:
            if tele.get_wire_type(w) != ZXWireType.Basic:
                continue
            ((u, u_port), (v, v_port)) = tele.get_wire_ends(w)
            gr_match = None
            if tele.get_zxtype(u) == ZXType.ZSpider and tele.get_zxtype(v) == ZXType.XSpider:
                gr_match = (u, v)
            elif tele.get_zxtype(u) == ZXType.XSpider and tele.get_zxtype(v) == ZXType.ZSpider:
                gr_match = (v, u)
            
            if gr_match:
                if gr_match in gr_edges:
                    # Found a matching pair, remove them
                    other_w = gr_edges[gr_match]
                    tele.remove_wire(w)
                    tele.remove_wire(other_w)
                    del gr_edges[gr_match]
                else:
                    # Record the edge for later
                    gr_edges[gr_match] = w
    
    strong_comp()

    gv.Source(tele.to_graphviz_str())

Finally, we write a procedure that finds spiders of degree 2 which act like an identity. We need to check that the phase on the spider is zero, and that the :py:class:`QuantumType` of the generator matches those of the incident edges (so we don't accidentally remove decoherence spiders).

.. jupyter-execute::

    def id_remove():
        for v in tele.vertices:
            if tele.degree(v) == 2 and tele.get_zxtype(v) in (ZXType.ZSpider, ZXType.XSpider):
                spid = tele.get_vertex_ZXGen(v)
                ws = tele.adj_wires(v)
                if spid.param == 0 and tele.get_wire_qtype(ws[0]) == spid.qtype and tele.get_wire_qtype(ws[1]) == spid.qtype:
                    # Found an identity
                    n0 = tele.other_end(ws[0], v)
                    n1 = tele.other_end(ws[1], v)
                    wtype = ZXWireType.H if (tele.get_wire_type(ws[0]) == ZXWireType.H) != (tele.get_wire_type(ws[1]) == ZXWireType.H) else ZXWireType.Basic
                    tele.add_wire(n0, n1, wtype, spid.qtype)
                    tele.remove_vertex(v)
    
    id_remove()

    gv.Source(tele.to_graphviz_str())

.. jupyter-execute::

    fuse()
    gv.Source(tele.to_graphviz_str())

.. jupyter-execute::

    strong_comp()
    gv.Source(tele.to_graphviz_str())

.. jupyter-execute::

    id_remove()
    gv.Source(tele.to_graphviz_str())

.. Removing vertices and edges versus editing in-place

A number of other methods for inspecting and traversing a diagram are available and can be found in the API reference.

Built-in Rewrite Passes
-----------------------

.. Not just individual rewrites but maximal (not necessarily exhaustive) applications

The pytket ZX module comes with a handful of common rewrite procedures built-in to prevent the need to write manual traversals in many cases. These procedures work in a similar way to the pytket compilation passes in applying a particular strategy across the entire diagram, saving computational time by potentially applying many rewrites in a single traversal. In the cases where there are overlapping patterns or rewrites that introduce new target patterns in the output diagram, these rewrites may not always be applied exhaustively to save time backtracking.

.. jupyter-execute::

    # This diagram follows from section A of https://arxiv.org/pdf/1902.03178.pdf
    diag = ZXDiagram(4, 4, 0, 0)
    ins = diag.get_boundary(ZXType.Input)
    outs = diag.get_boundary(ZXType.Output)
    v11 = diag.add_vertex(ZXType.ZSpider, 1.5)
    v12 = diag.add_vertex(ZXType.ZSpider, 0.5)
    v13 = diag.add_vertex(ZXType.ZSpider)
    v14 = diag.add_vertex(ZXType.XSpider)
    v15 = diag.add_vertex(ZXType.ZSpider, 0.25)
    v21 = diag.add_vertex(ZXType.ZSpider, 0.5)
    v22 = diag.add_vertex(ZXType.ZSpider)
    v23 = diag.add_vertex(ZXType.ZSpider)
    v24 = diag.add_vertex(ZXType.ZSpider, 0.25)
    v25 = diag.add_vertex(ZXType.ZSpider)
    v31 = diag.add_vertex(ZXType.XSpider)
    v32 = diag.add_vertex(ZXType.XSpider)
    v33 = diag.add_vertex(ZXType.ZSpider, 0.5)
    v34 = diag.add_vertex(ZXType.ZSpider, 0.5)
    v35 = diag.add_vertex(ZXType.XSpider)
    v41 = diag.add_vertex(ZXType.ZSpider)
    v42 = diag.add_vertex(ZXType.ZSpider)
    v43 = diag.add_vertex(ZXType.ZSpider, 1.5)
    v44 = diag.add_vertex(ZXType.XSpider, 1.0)
    v45 = diag.add_vertex(ZXType.ZSpider, 0.5)
    v46 = diag.add_vertex(ZXType.XSpider, 1.0)

    diag.add_wire(ins[0], v11)
    diag.add_wire(v11, v12, ZXWireType.H)
    diag.add_wire(v12, v13)
    diag.add_wire(v13, v41, ZXWireType.H)
    diag.add_wire(v13, v14)
    diag.add_wire(v14, v42)
    diag.add_wire(v14, v15, ZXWireType.H)
    diag.add_wire(v15, outs[0], ZXWireType.H)

    diag.add_wire(ins[1], v21)
    diag.add_wire(v21, v22)
    diag.add_wire(v22, v31)
    diag.add_wire(v22, v23, ZXWireType.H)
    diag.add_wire(v23, v32)
    diag.add_wire(v23, v24)
    diag.add_wire(v24, v25, ZXWireType.H)
    diag.add_wire(v25, v35)
    diag.add_wire(outs[1], v25)

    diag.add_wire(ins[2], v31)
    diag.add_wire(v31, v32)
    diag.add_wire(v32, v33)
    diag.add_wire(v33, v34, ZXWireType.H)
    diag.add_wire(v34, v35)
    diag.add_wire(v35, outs[2])

    diag.add_wire(ins[3], v41, ZXWireType.H)
    diag.add_wire(v41, v42)
    diag.add_wire(v42, v43, ZXWireType.H)
    diag.add_wire(v43, v44)
    diag.add_wire(v44, v45)
    diag.add_wire(v45, v46)
    diag.add_wire(v46, outs[3])
    diag.check_validity()

    gv.Source(diag.to_graphviz_str())

.. jupyter-execute::

    from pytket.zx import Rewrite
    
    Rewrite.red_to_green().apply(diag)
    Rewrite.spider_fusion().apply(diag)
    Rewrite.io_extension().apply(diag)
    gv.Source(diag.to_graphviz_str())

.. jupyter-execute::

    Rewrite.reduce_graphlike_form().apply(diag)
    gv.Source(diag.to_graphviz_str())

.. Intended to support common optimisation strategies; focussed on reducing to specific forms and work in graphlike form

The particular rewrites available are intended to support common optimisation strategies. In particular, they mostly focus on converting a diagram to graphlike form and working on graphlike diagrams to reduce the number of vertices as much as possible. These have close correspondences with MBQC patterns, and the rewrites preserve the existence of flow, which helps guarantee an efficient extraction procedure.

.. May not work as intended if diagram is not in intended form, especially for classical or mixed diagrams

.. warning:: Because of the focus on strategies using graphlike diagrams, many of the rewrites expect the inputs to be of a particular form. This may cause some issues if you attempt to apply them to diagrams that aren't in the intended form, especially when working with classical or mixed diagrams.

.. Types (decompositions into generating sets, graphlike form, graphlike reduction, MBQC)

The rewrite passes can be broken down into a few categories depending on the form of the diagrams expected and the function of the passes. Full descriptions of each pass are given in the API reference.

=================================== ===========================================
Decompositions into generating sets 
                                      :py:meth:`Rewrite.decompose_boxes()`, 
                                      :py:meth:`Rewrite.basic_wires()`, 
                                      :py:meth:`Rewrite.rebase_to_zx()`, 
                                      :py:meth:`Rewrite.rebase_to_mbqc()`
Rewriting into graphlike form       
                                      :py:meth:`Rewrite.red_to_green()`,
                                      :py:meth:`Rewrite.spider_fusion()`,
                                      :py:meth:`Rewrite.self_loop_removal()`,
                                      :py:meth:`Rewrite.parallel_h_removal()`,
                                      :py:meth:`Rewrite.separate_boundaries()`,
                                      :py:meth:`Rewrite.io_extension()`
Reduction within graphlike form     
                                      :py:meth:`Rewrite.remove_interior_cliffords()`,
                                      :py:meth:`Rewrite.remove_interior_paulis()`, 
                                      :py:meth:`Rewrite.gadgetise_interior_paulis()`, 
                                      :py:meth:`Rewrite.merge_gadgets()`, 
                                      :py:meth:`Rewrite.extend_at_boundary_paulis()`
MBQC                                
                                      :py:meth:`Rewrite.extend_for_PX_outputs()`, 
                                      :py:meth:`Rewrite.internalise_gadgets()`
Composite sequences                 
                                      :py:meth:`Rewrite.to_graphlike_form()`,
                                      :py:meth:`Rewrite.reduce_graphlike_form()`,
                                      :py:meth:`Rewrite.to_MBQC_diag()`
=================================== ===========================================

.. Current implementations may not track global scalar; semantics is only preserved up to scalar; warning if attempting to use for scalar diagram evaluation

.. warning:: Current implementations of rewrite passes may not track the global scalar. Semantics of diagrams is only preserved up to scalar. This is fine for simplification of states or unitaries as they can be renormalised but this may cause issues if attempting to use rewrites for scalar diagram evaluation.

MBQC Flow Detection
-------------------

.. MBQC form of diagrams

So far, we have focussed mostly on the circuit model of quantum computing, but the ZX module is also geared towards assisting for MBQC. The most practical measurement patterns are those with uniform, stepwise, strong determinism - that is, performing an individual measurement and its associated corrections will yield exactly the same residual state, and furthermore this is the case for any choice of angle parameter the qubit is measured in (within a particular plane of the Bloch sphere or choice of polarity of a Pauli measurement, according to the label of the measurement). In this case, the order of measurements and corrections can be described by a Flow over the entanglement graph.

.. MBQC diagrams only show intended branch, order and corrections handled by flow

When using the ZX module to represent measurement patterns, we care about representing the semantics and so it is sufficient to consider post-selecting the intended branch outcome at each qubit. This simplifies the diagram by eliminating the corrections and any need to track the order of measurements internally to the diagram. Instead, we may track these externally using a :py:class:`Flow` object.

Each of the MBQC :py:class:`ZXType` options represent a qubit that is initialised and post-selected into the plane/Pauli specified by the type, at the angle/polarity given by the parameter of the :py:class:`ZXGen`. Entanglement between these qubits is given by :py:class:`ZXWireType.H` edges, representing CZ gates. We identify input and output qubits using :py:class:`ZXWireType.Basic` edges connecting them to :py:class:`ZXType.Input` or :py:class:`ZXType.Output` vertices (since output qubits are unmeasured, their semantics as tensors are equivalent to :py:class:`ZXType.PX` vertices with ``False`` polarity). The :py:meth:`Rewrite.to_MBQC_diag()` rewrite will transform any ZX diagram into one of this form.

.. jupyter-execute::

    Rewrite.to_MBQC_diag().apply(diag)
    gv.Source(diag.to_graphviz_str())

.. Causal flow, gflow, Pauli flow (completeness of extended Pauli flow and hence Pauli flow)

Given a ZX diagram in MBQC form, there are algorithms that can find a suitable :py:class:`Flow` if one exists. Since there are several classifications of flow (e.g. causal flow, gflow, Pauli flow, extended Pauli flow) with varying levels of generality, we offer multiple algorithms for identifying them. For example, any diagram supporting a uniform, stepwise, strongly deterministic measurement and correction scheme will have a Pauli flow, but identification of this is :math:`O(n^4)` in the number of qubits (vertices) in the pattern. On the other hand, causal flow is a particular special case that may not always exist but can be identified in :math:`O(n^2 \log n)` time.

The :py:class:`Flow` object that is returned abstracts away the partial ordering of the measured qubits of the diagram by just giving the depth from the outputs, i.e. all output qubits and those with no corrections have depth :math:`0`, all qubits with depth :math:`n` can be measured simultaneously and only require corrections on qubits at depth strictly less than :math:`n`. The measurement corrections can also be inferred from the flow, where :py:meth:`Flow.c()` gives the correction set for a given measured qubit (the qubits which require an :math:`X` correction if a measurement error occurs) and :py:meth:`Flow.odd()` gives its odd neighbourhood (the qubits which require a :math:`Z` correction).

.. jupyter-execute::

    from pytket.zx import Flow

    fl = Flow.identify_pauli_flow(diag)

    # We can look up the flow data for a particular vertex
    # For example, let's take the first input qubit
    vertex_ids = { v : i for (i, v) in enumerate(diag.vertices) }
    in0 = diag.get_boundary(ZXType.Input)[0]
    v = diag.neighbours(in0)[0]
    print(vertex_ids[v])
    print(fl.d(v))
    print([vertex_ids[c] for c in fl.c(v)])
    print([vertex_ids[o] for o in fl.odd(v, diag)])

    # Or we can obtain the entire flow as maps for easy iteration
    print({ vertex_ids[v] : d for (v, d) in fl.dmap.items() })
    print({ vertex_ids[v] : [vertex_ids[c] for c in cs] for (v, cs) in fl.cmap.items() })

.. note:: In accordance with the Pauli flow criteria, :py:meth:`Flow.c()` and :py:meth:`Flow.odd()` may return qubits that have already been measured, but this may only happen in cases where the required correction would not have affected the past measurement such as a :math:`Z` on a :py:class:`ZXType.PZ` qubit.

.. Verification and focussing

In general, multiple valid flows may exist for a given diagram, but a pattern with equal numbers of inputs and outputs will always have a unique focussed flow (where the corrections permitted on each qubit are restricted to be a single Pauli based on its label, e.g. if qubit :math:`q` is labelled as :py:class:`ZXType.XY`, then we may only apply :math:`X` corrections to :math:`q`). Given any flow, we may transform it to a focussed flow using :py:meth:`Flow.focus()`.

.. Warning that does not update on rewriting

.. warning:: A :py:class:`Flow` object is always with respect to a particular :py:class:`ZXDiagram` in a particular state. It cannot be applied to other diagrams and does not automatically update on rewriting the diagram.

Conversions & Extraction
------------------------

.. Circuits to ZX diagram by gate definitions

Up to this point, we have only examined the ZX module in a vacuum, so now we will look at integrating it with the rest of tket's functionality by converting between :py:class:`ZXDiagram` and :py:class:`~pytket.circuit.Circuit` objects. The :py:meth:`circuit_to_zx()` function will reconstruct a :py:class:`~pytket.circuit.Circuit` as a :py:class:`ZXDiagram` by replacing each gate with a choice of representation in the ZX-calculus.

.. Created and discarded qubits are not open boundaries; indexing of boundaries made by qubit and bit order; conversion returns a map between boundaries and UnitIDs

The boundaries of the resulting :py:class:`ZXDiagram` will match up with the open boundaries of the :py:class:`~pytket.circuit.Circuit`. However, :py:class:`OpType.Create` and :py:class:`OpType.Discard` operations will be replaced with an initialisation and a discard map respectively, meaning the number of boundary vertices in the resulting diagram may not match up with the number of qubits and bits in the original :py:class:`~pytket.circuit.Circuit`. This makes it difficult to have a sensible policy for knowing where in the linear boundary of the :py:class:`ZXDiagram` is the input/output of a particular qubit. The second return value of :py:meth:`circuit_to_zx()` is a map sending a :py:class:`UnitID` to the pair of :py:class:`ZXVert` objects for the corresponding input and output.

.. jupyter-execute::

    from pytket import Circuit, Qubit
    from pytket.zx import circuit_to_zx

    c = Circuit(4)
    c.CZ(0, 1)
    c.CX(1, 2)
    c.H(1)
    c.X(0)
    c.Rx(0.7, 0)
    c.Rz(0.2, 1)
    c.X(3)
    c.H(2)
    c.qubit_create(Qubit(2))
    c.qubit_discard(Qubit(3))
    diag, bound_map = circuit_to_zx(c)

    in3, out3 = bound_map[Qubit(3)]
    # Qubit 3 was discarded, so out3 won't give a vertex
    # Look at the neighbour of the input to check the first operation is the X
    n = diag.neighbours(in3)[0]
    print(diag.get_vertex_ZXGen(n))

.. Extraction is not computationally feasible for general diagrams; known to be efficient for MBQC diagrams with flow; current method permits unitary diagrams with gflow, based on Backens et al.; more methods will be written in future for different extraction methods, e.g. causal flow, MBQC, pauli flow, mixed diagram extraction

From here, we are able to rewrite our circuit as a ZX diagram, and even though we may aim to preserve the semantics, there is often little guarantee that the diagram will resemble the structure of a circuit after rewriting. The extraction problem concerns taking a ZX diagram and attempting to identify an equivalent circuit, and this is known to be #P-Hard for arbitrary diagrams equivalent to a unitary circuit which is not computationally feasible. However, if we can guarantee that our rewriting leaves us with a diagram in MBQC form which admits a flow of some kind, then there exist efficient methods for extracting an equivalent circuit.

The current method implemented in :py:meth:`ZXDiagram.to_circuit()` permits extraction of a circuit from a unitary ZX diagram with gflow, based on the method of Backens et al. [Back2021]_. More methods may be added in the future for different extraction methods, such as fast extraction with causal flow, MBQC (i.e. a :py:class:`~pytket.circuit.Circuit` with explicit measurement and correction operations), extraction from Pauli flow, and mixed diagram extraction.

Since the :py:class:`ZXDiagram` class does not associate a :py:class:`UnitID` to each boundary vertex, :py:meth:`ZXDiagram.to_circuit()` also returns a map sending each boundary :py:class:`ZXVert` to the corresponding :py:class:`UnitID` in the resulting :py:class:`~pytket.circuit.Circuit`.

.. jupyter-execute::

    from pytket import OpType
    from pytket.circuit.display import render_circuit_jupyter
    from pytket.passes import auto_rebase_pass

    c = Circuit(5)
    c.CCX(0, 1, 4)
    c.CCX(2, 4, 3)
    c.CCX(0, 1, 4)
    # Conversion is only defined for a subset of gate types - rebase as needed
    auto_rebase_pass({ OpType.Rx, OpType.Rz, OpType.X, OpType.Z, OpType.H, OpType.CZ, OpType.CX }).apply(c)
    diag, _ = circuit_to_zx(c)

    Rewrite.to_graphlike_form().apply(diag)
    Rewrite.reduce_graphlike_form().apply(diag)

    # Extraction requires the diagram to use MBQC generators
    Rewrite.to_MBQC_diag().apply(diag)
    circ, _ = diag.to_circuit()
    render_circuit_jupyter(circ)

Compiler Passes Using ZX
------------------------

.. Prepackaged into ZXGraphlikeOptimisation pass for convenience to try out 

The known methods for circuit rewriting and optimisation lend themselves to a single common routine of mapping to graphlike form, reducing within that form, and extracting back out. :py:class:`ZXGraphlikeOptimisation` is a standard pytket compiler pass that packages this routine up for convenience to save the user from manually digging into the ZX module before they can test out using the compilation routine on their circuits.

.. jupyter-execute::

    from pytket.passes import ZXGraphlikeOptimisation

    # Use the same CCX example from above
    ZXGraphlikeOptimisation().apply(c)
    render_circuit_jupyter(c)

The specific nature of optimising circuits via ZX diagrams gives rise to some general advice regarding how to use :py:class:`ZXGraphlikeOptimisation` in compilation sequences and what to expect from its performance:

.. Extraction techniques are not optimal so starting with a well-structured circuit, abstracting away that structure and starting from scratch is likely to increase gate counts; since graphlike form abstracts away Cliffords to focus on non-Cliffords, most likely to give good results on Clifford-dense circuits

* The routine can broadly be thought of as a resynthesis pass: converting to a graphlike ZX diagram completely abstracts away most of the circuit structure and attempts to extract a new circuit from scratch. Coupling this with the difficulty of optimal extraction means that if the original circuit is already well-structured or close to optimal, it is likely that the process of forgetting that structure and trying to extract something new will increase gate counts. Since the graphlike form abstracts away the structure from Clifford gates to focus on the non-Cliffords, it is most likely going to give its best results on very Clifford-dense circuits. Even in cases where this improves on gate counts, it may be the case that the new circuit structure is harder to efficiently route on a device with restricted qubit connectivity, so it is important to consider the context of a full compilation sequence when analysing the benefits of using this routine.

.. Since ZX does resynthesis and completely abstracts away circuit structure, there is little point in running optimisations before ZX

* Similarly, because the conversion to a graphlike ZX diagram completely abstracts away the Clifford gates, there is often little-to-no benefit in running most simple optimisations before applying :py:class:`ZXGraphlikeOptimisation` since it will largely ignore them and achieve the same graphlike form regardless.

.. Extraction is not optimised so best to run other passes afterwards

* The implementation of the extraction routine in pytket follows the steps from Backens et al. [Back2021]_ very closely without optimising the gate sequences as they are produced. It is recommended to run additional peephole optimisation passes afterwards to account for redundancies introduced by the extraction procedure. For example, we can see in the above example that there are many sequences of successive Hadamard gates that could be removed using a pass like :py:class:`RemoveRedundancies`. :py:class:`~pytket.passes.FullPeepholeOptimise` is a good catch-all that incorporates many peephole optimisations and could further reduce the extracted circuit. 

Advanced Topics
---------------

C++ Implementation
==================

.. Use for speed and more control

As with the rest of pytket, the ZX module features a python interface that has enough flexibility to realise any diagram a user would wish to construct or a rewrite they would like to apply, but the data structure itself is defined in the core C++ library for greater speed for longer rewrite passes and analysis tasks. This comes with the downside that interacting via the python interface is slowed down by the need to convert data through the bindings. After experimenting with the python interface and devising new rewrite strategies, we recommend users use the C++ library directly for speed and greater control over the data structure when attempting to write heavy-duty implementations that require the use of this module's unique features (for simpler rewriting tasks, it may be faster to use ``quizx`` [https://github.com/Quantomatic/quizx] which sacrifices some flexibility for even more performance).

.. Underlying graph structure is directed to distinguish between ends of an edge for port data

The interface to the ``ZXDiagram`` C++ class is extremely similar to the python interface. The main difference is that, whilst the edges of a ZX diagram are semantically undirected, the underlying data structure for the graph itself uses directed edges. This allows us to attach the port data for an edge to the edge metadata and distinguish between its two end-points by referring to the source and target of the edge - for example, an edge between :math:`(u,1)` and :math:`(v,-)` (where :math:`v` is a symmetric generator without port information) can be represented as an edge from :math:`u` to :math:`v` whose metadata carries ``(source_port = 1, target_port = std::nullopt)``.

.. Tensor evaluation only available in python, so easiest to expose in pybind for testing

When implementing a rewrite in C++, we recommend exposing your method via the pybind interface and testing it using pytket when possible. The primary reason for this is that the tensor evaluation available uses the ``quimb`` python package to scale to large numbers of nodes in the tensor network, which is particularly useful for testing that your rewrite preserves the diagram semantics.

In place of API reference and code examples, we recommend looking at the following parts of the tket source code to see how the ZX module is already used:

* ZXDiagram.hpp gives inline summaries for the interface to the core diagram data structure.

* ``Rewrite::spider_fusion_fun()`` in ZXRWAxioms.cpp is an example of a simple rewrite that is applied across the entire graph by iterating over each vertex and looking for patterns in its immediate neighbourhood. It demonstrates the relevance of checking edge data for its :py:class:`ZXWireType` and :py:class:`QuantumType` and maintaining track of these throughout a rewrite.

* ``Rewrite::remove_interior_paulis_fun()`` in ZXRWGraphLikeSimplification.cpp demonstrates how the checks and management of the format of vertices and edges can be simplified a little once it is established that the diagram is of a particular form (e.g. graphlike).

* ``ZXGraphlikeOptimisation()`` in PassLibrary.cpp uses a sequence of rewrites along with the converters to build a compilation pass for circuits. Most of the method contents is just there to define the expectations of the form of the circuit using the tket :py:class:`~pytket.predicates.Predicate` system, which saves the need for the pass to be fully generic and be constantly maintained to accept arbitrary circuits.

* ``zx_to_circuit()`` in ZXConverters.cpp implements the extraction procedure. It is advised to read this alongside the algorithm description in Backens et al. for more detail on the intent and intuition around each step.


.. [Back2021] Backens, M. et al., 2021. There and back again: A circuit extraction tale. Quantum, 5, p.451.

.. [vdWet2020] van de Wetering, J., 2020. ZX-calculus for the working quantum computer scientist. https://arxiv.org/abs/2012.13966
