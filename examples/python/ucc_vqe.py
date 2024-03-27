# # VQE with UCC ansatz

# In this tutorial, we will focus on:
# - building parameterised ansätze for variational algorithms;
# - compilation tools for UCC-style ansätze.

# This example assumes the reader is familiar with the Variational Quantum Eigensolver and its application to electronic structure problems through the Unitary Coupled Cluster approach.
#
# To run this example, you will need `pytket` and `pytket-qiskit`, as well as `openfermion`, `scipy`, and `sympy`.
#
# We will start with a basic implementation and then gradually modify it to make it faster, more general, and less noisy. The final solution is given in full at the bottom of the notebook.
#
# Suppose we have some electronic configuration problem, expressed via a physical Hamiltonian. (The Hamiltonian and excitations in this example were obtained using `qiskit-aqua` version 0.5.2 and `pyscf` for H2, bond length 0.75A, sto3g basis, Jordan-Wigner encoding, with no qubit reduction or orbital freezing.). We express it succinctly using the openfermion library:

import openfermion as of

hamiltonian = (
    -0.8153001706270075 * of.QubitOperator("")
    + 0.16988452027940318 * of.QubitOperator("Z0")
    + -0.21886306781219608 * of.QubitOperator("Z1")
    + 0.16988452027940323 * of.QubitOperator("Z2")
    + -0.2188630678121961 * of.QubitOperator("Z3")
    + 0.12005143072546047 * of.QubitOperator("Z0 Z1")
    + 0.16821198673715723 * of.QubitOperator("Z0 Z2")
    + 0.16549431486978672 * of.QubitOperator("Z0 Z3")
    + 0.16549431486978672 * of.QubitOperator("Z1 Z2")
    + 0.1739537877649417 * of.QubitOperator("Z1 Z3")
    + 0.12005143072546047 * of.QubitOperator("Z2 Z3")
    + 0.04544288414432624 * of.QubitOperator("X0 X1 X2 X3")
    + 0.04544288414432624 * of.QubitOperator("X0 X1 Y2 Y3")
    + 0.04544288414432624 * of.QubitOperator("Y0 Y1 X2 X3")
    + 0.04544288414432624 * of.QubitOperator("Y0 Y1 Y2 Y3")
)
nuclear_repulsion_energy = 0.70556961456

# We would like to define our ansatz for arbitrary parameter values. For simplicity, let's start with a Hardware Efficient Ansatz.

from pytket import Circuit

# Hardware efficient ansatz:


def hea(params):
    ansatz = Circuit(4)
    for i in range(4):
        ansatz.Ry(params[i], i)
    for i in range(3):
        ansatz.CX(i, i + 1)
    for i in range(4):
        ansatz.Ry(params[4 + i], i)
    return ansatz


# We can use this to build the objective function for our optimisation.

from pytket.extensions.qiskit import AerBackend
from pytket.utils.expectations import expectation_from_counts

backend = AerBackend()

# Naive objective function:


def objective(params):
    energy = 0
    for term, coeff in hamiltonian.terms.items():
        if not term:
            energy += coeff
            continue
        circ = hea(params)
        circ.add_c_register("c", len(term))
        for i, (q, pauli) in enumerate(term):
            if pauli == "X":
                circ.H(q)
            elif pauli == "Y":
                circ.V(q)
            circ.Measure(q, i)
        compiled_circ = backend.get_compiled_circuit(circ)
        counts = backend.run_circuit(compiled_circ, n_shots=4000).get_counts()
        energy += coeff * expectation_from_counts(counts)
    return energy + nuclear_repulsion_energy


# This objective function is then run through a classical optimiser to find the set of parameter values that minimise the energy of the system. For the sake of example, we will just run this with a single parameter value.

arg_values = [
    -7.31158201e-02,
    -1.64514836e-04,
    1.12585591e-03,
    -2.58367544e-03,
    1.00006068e00,
    -1.19551357e-03,
    9.99963988e-01,
    2.53283285e-03,
]

energy = objective(arg_values)
print(energy)

# The HEA is designed to cram as many orthogonal degrees of freedom into a small circuit as possible to be able to explore a large region of the Hilbert space whilst the circuits themselves can be run with minimal noise. These ansätze give virtually-optimal circuits by design, but suffer from an excessive number of variational parameters making convergence slow, barren plateaus where the classical optimiser fails to make progress, and spanning a space where most states lack a physical interpretation. These drawbacks can necessitate adding penalties and may mean that the ansatz cannot actually express the true ground state.
#
# The UCC ansatz, on the other hand, is derived from the electronic configuration. It sacrifices efficiency of the circuit for the guarantee of physical states and the variational parameters all having some meaningful effect, which helps the classical optimisation to converge.
#
# This starts by defining the terms of our single and double excitations. These would usually be generated using the orbital configurations, so we will just use a hard-coded example here for the purposes of demonstration.

from pytket.circuit import Qubit
from pytket.pauli import Pauli, QubitPauliString

q = [Qubit(i) for i in range(4)]
xyii = QubitPauliString([q[0], q[1]], [Pauli.X, Pauli.Y])
yxii = QubitPauliString([q[0], q[1]], [Pauli.Y, Pauli.X])
iixy = QubitPauliString([q[2], q[3]], [Pauli.X, Pauli.Y])
iiyx = QubitPauliString([q[2], q[3]], [Pauli.Y, Pauli.X])
xxxy = QubitPauliString(q, [Pauli.X, Pauli.X, Pauli.X, Pauli.Y])
xxyx = QubitPauliString(q, [Pauli.X, Pauli.X, Pauli.Y, Pauli.X])
xyxx = QubitPauliString(q, [Pauli.X, Pauli.Y, Pauli.X, Pauli.X])
yxxx = QubitPauliString(q, [Pauli.Y, Pauli.X, Pauli.X, Pauli.X])
yyyx = QubitPauliString(q, [Pauli.Y, Pauli.Y, Pauli.Y, Pauli.X])
yyxy = QubitPauliString(q, [Pauli.Y, Pauli.Y, Pauli.X, Pauli.Y])
yxyy = QubitPauliString(q, [Pauli.Y, Pauli.X, Pauli.Y, Pauli.Y])
xyyy = QubitPauliString(q, [Pauli.X, Pauli.Y, Pauli.Y, Pauli.Y])

singles_a = {xyii: 1.0, yxii: -1.0}
singles_b = {iixy: 1.0, iiyx: -1.0}
doubles = {
    xxxy: 0.25,
    xxyx: -0.25,
    xyxx: 0.25,
    yxxx: -0.25,
    yyyx: -0.25,
    yyxy: 0.25,
    yxyy: -0.25,
    xyyy: 0.25,
}

# Building the ansatz circuit itself is often done naively by defining the map from each term down to basic gates and then applying it to each term.


def add_operator_term(circuit: Circuit, term: QubitPauliString, angle: float):
    qubits = []
    for q, p in term.map.items():
        if p != Pauli.I:
            qubits.append(q)
            if p == Pauli.X:
                circuit.H(q)
            elif p == Pauli.Y:
                circuit.V(q)
    for i in range(len(qubits) - 1):
        circuit.CX(i, i + 1)
    circuit.Rz(angle, len(qubits) - 1)
    for i in reversed(range(len(qubits) - 1)):
        circuit.CX(i, i + 1)
    for q, p in term.map.items():
        if p == Pauli.X:
            circuit.H(q)
        elif p == Pauli.Y:
            circuit.Vdg(q)


# Unitary Coupled Cluster Singles & Doubles ansatz:


def ucc(params):
    ansatz = Circuit(4)
    # Set initial reference state
    ansatz.X(1).X(3)
    # Evolve by excitations
    for term, coeff in singles_a.items():
        add_operator_term(ansatz, term, coeff * params[0])
    for term, coeff in singles_b.items():
        add_operator_term(ansatz, term, coeff * params[1])
    for term, coeff in doubles.items():
        add_operator_term(ansatz, term, coeff * params[2])
    return ansatz


# This is already quite verbose, but `pytket` has a neat shorthand construction for these operator terms using the `PauliExpBox` construction. We can then decompose these into basic gates using the `DecomposeBoxes` compiler pass.

from pytket.circuit import PauliExpBox
from pytket.passes import DecomposeBoxes


def add_excitation(circ, term_dict, param):
    for term, coeff in term_dict.items():
        qubits, paulis = zip(*term.map.items())
        pbox = PauliExpBox(paulis, coeff * param)
        circ.add_gate(pbox, qubits)


# UCC ansatz with syntactic shortcuts:


def ucc(params):
    ansatz = Circuit(4)
    ansatz.X(1).X(3)
    add_excitation(ansatz, singles_a, params[0])
    add_excitation(ansatz, singles_b, params[1])
    add_excitation(ansatz, doubles, params[2])
    DecomposeBoxes().apply(ansatz)
    return ansatz


# The objective function can also be simplified using a utility method for constructing the measurement circuits and processing for expectation value calculations. For that, we convert the Hamiltonian to a pytket QubitPauliOperator:

from pytket.utils.operators import QubitPauliOperator


pauli_sym = {"I": Pauli.I, "X": Pauli.X, "Y": Pauli.Y, "Z": Pauli.Z}


def qps_from_openfermion(paulis):
    """Convert OpenFermion tensor of Paulis to pytket QubitPauliString."""
    qlist = []
    plist = []
    for q, p in paulis:
        qlist.append(Qubit(q))
        plist.append(pauli_sym[p])
    return QubitPauliString(qlist, plist)


def qpo_from_openfermion(openf_op):
    """Convert OpenFermion QubitOperator to pytket QubitPauliOperator."""
    tk_op = dict()
    for term, coeff in openf_op.terms.items():
        string = qps_from_openfermion(term)
        tk_op[string] = coeff
    return QubitPauliOperator(tk_op)


hamiltonian_op = qpo_from_openfermion(hamiltonian)

# Simplified objective function using utilities:
from pytket.utils.expectations import get_operator_expectation_value


def objective(params):
    circ = ucc(params)
    return (
        get_operator_expectation_value(circ, hamiltonian_op, backend, n_shots=4000)
        + nuclear_repulsion_energy
    )


arg_values = [-3.79002933e-05, 2.42964799e-05, 4.63447157e-01]

energy = objective(arg_values)
print(energy)

# This is now the simplest form that this operation can take, but it isn't necessarily the most effective. When we decompose the ansatz circuit into basic gates, it is still very expensive. We can employ some of the circuit simplification passes available in `pytket` to reduce its size and improve fidelity in practice.
#
# A good example is to decompose each `PauliExpBox` into basic gates and then apply `FullPeepholeOptimise`, which defines a compilation strategy utilising all of the simplifications in `pytket` that act locally on small regions of a circuit. We can examine the effectiveness by looking at the number of two-qubit gates before and after simplification, which tends to be a good indicator of fidelity for near-term systems where these gates are often slow and inaccurate.

from pytket import OpType
from pytket.passes import FullPeepholeOptimise

test_circuit = ucc(arg_values)

print("CX count before", test_circuit.n_gates_of_type(OpType.CX))
print("CX depth before", test_circuit.depth_by_type(OpType.CX))

FullPeepholeOptimise().apply(test_circuit)

print("CX count after FPO", test_circuit.n_gates_of_type(OpType.CX))
print("CX depth after FPO", test_circuit.depth_by_type(OpType.CX))

# These simplification techniques are very general and are almost always beneficial to apply to a circuit if you want to eliminate local redundancies. But UCC ansätze have extra structure that we can exploit further. They are defined entirely out of exponentiated tensors of Pauli matrices, giving the regular structure described by the `PauliExpBox`es. Under many circumstances, it is more efficient to not synthesise these constructions individually, but simultaneously in groups. The `PauliSimp` pass finds the description of a given circuit as a sequence of `PauliExpBox`es and resynthesises them (by default, in groups of commuting terms). This can cause great change in the overall structure and shape of the circuit, enabling the identification and elimination of non-local redundancy.

from pytket.passes import PauliSimp

test_circuit = ucc(arg_values)

print("CX count before", test_circuit.n_gates_of_type(OpType.CX))
print("CX depth before", test_circuit.depth_by_type(OpType.CX))

PauliSimp().apply(test_circuit)

print("CX count after PS", test_circuit.n_gates_of_type(OpType.CX))
print("CX depth after PS", test_circuit.depth_by_type(OpType.CX))

FullPeepholeOptimise().apply(test_circuit)

print("CX count after PS+FPO", test_circuit.n_gates_of_type(OpType.CX))
print("CX depth after PS+FPO", test_circuit.depth_by_type(OpType.CX))

# To include this into our routines, we can just add the simplification passes to the objective function. The `get_operator_expectation_value` utility handles compiling to meet the requirements of the backend, so we don't have to worry about that here.

# Objective function with circuit simplification:


def objective(params):
    circ = ucc(params)
    PauliSimp().apply(circ)
    FullPeepholeOptimise().apply(circ)
    return (
        get_operator_expectation_value(circ, hamiltonian_op, backend, n_shots=4000)
        + nuclear_repulsion_energy
    )


# These circuit simplification techniques have tried to preserve the exact unitary of the circuit, but there are ways to change the unitary whilst preserving the correctness of the algorithm as a whole.
#
# For example, the excitation terms are generated by trotterisation of the excitation operator, and the order of the terms does not change the unitary in the limit of many trotter steps, so in this sense we are free to sequence the terms how we like and it is sensible to do this in a way that enables efficient synthesis of the circuit. Prioritising collecting terms into commuting sets is a very beneficial heuristic for this and can be performed using the `gen_term_sequence_circuit` method to group the terms together into collections of `PauliExpBox`es and the `GuidedPauliSimp` pass to utilise these sets for synthesis.

from pytket.passes import GuidedPauliSimp
from pytket.utils import gen_term_sequence_circuit


def ucc(params):
    singles_params = {qps: params[0] * coeff for qps, coeff in singles.items()}
    doubles_params = {qps: params[1] * coeff for qps, coeff in doubles.items()}
    excitation_op = QubitPauliOperator({**singles_params, **doubles_params})
    reference_circ = Circuit(4).X(1).X(3)
    ansatz = gen_term_sequence_circuit(excitation_op, reference_circ)
    GuidedPauliSimp().apply(ansatz)
    FullPeepholeOptimise().apply(ansatz)
    return ansatz


# Adding these simplification routines doesn't come for free. Compiling and simplifying the circuit to achieve the best results possible can be a difficult task, which can take some time for the classical computer to perform.
#
# During a VQE run, we will call this objective function many times and run many measurement circuits within each, but the circuits that are run on the quantum computer are almost identical, having the same gate structure but with different gate parameters and measurements. We have already exploited this within the body of the objective function by simplifying the ansatz circuit before we call `get_operator_expectation_value`, so it is only done once per objective calculation rather than once per measurement circuit.
#
# We can go even further by simplifying it once outside of the objective function, and then instantiating the simplified ansatz with the parameter values needed. For this, we will construct the UCC ansatz circuit using symbolic (parametric) gates.

from sympy import symbols

# Symbolic UCC ansatz generation:

syms = symbols("p0 p1 p2")
singles_a_syms = {qps: syms[0] * coeff for qps, coeff in singles_a.items()}
singles_b_syms = {qps: syms[1] * coeff for qps, coeff in singles_b.items()}
doubles_syms = {qps: syms[2] * coeff for qps, coeff in doubles.items()}
excitation_op = QubitPauliOperator({**singles_a_syms, **singles_b_syms, **doubles_syms})
ucc_ref = Circuit(4).X(1).X(3)
ucc = gen_term_sequence_circuit(excitation_op, ucc_ref)
GuidedPauliSimp().apply(ucc)
FullPeepholeOptimise().apply(ucc)

# Objective function using the symbolic ansatz:


def objective(params):
    circ = ucc.copy()
    sym_map = dict(zip(syms, params))
    circ.symbol_substitution(sym_map)
    return (
        get_operator_expectation_value(circ, hamiltonian_op, backend, n_shots=4000)
        + nuclear_repulsion_energy
    )


# We have now got some very good use of `pytket` for simplifying each individual circuit used in our experiment and for minimising the amount of time spent compiling, but there is still more we can do in terms of reducing the amount of work the quantum computer has to do. Currently, each (non-trivial) term in our measurement hamiltonian is measured by a different circuit within each expectation value calculation. Measurement reduction techniques exist for identifying when these observables commute and hence can be simultaneously measured, reducing the number of circuits required for the full expectation value calculation.
#
# This is built in to the `get_operator_expectation_value` method and can be applied by specifying a way to partition the measuremrnt terms. `PauliPartitionStrat.CommutingSets` can greatly reduce the number of measurement circuits by combining any number of terms that mutually commute. However, this involves potentially adding an arbitrary Clifford circuit to change the basis of the measurements which can be costly on NISQ devices, so `PauliPartitionStrat.NonConflictingSets` trades off some of the reduction in circuit number to guarantee that only single-qubit gates are introduced.

from pytket.partition import PauliPartitionStrat

# Objective function using measurement reduction:


def objective(params):
    circ = ucc.copy()
    sym_map = dict(zip(syms, params))
    circ.symbol_substitution(sym_map)
    return (
        get_operator_expectation_value(
            circ,
            operator,
            backend,
            n_shots=4000,
            partition_strat=PauliPartitionStrat.CommutingSets,
        )
        + nuclear_repulsion_energy
    )


# At this point, we have completely transformed how our VQE objective function works, improving its resilience to noise, cutting the number of circuits run, and maintaining fast runtimes. In doing this, we have explored a number of the features `pytket` offers that are beneficial to VQE and the UCC method:
# - high-level syntactic constructs for evolution operators;
# - utility methods for easy expectation value calculations;
# - both generic and domain-specific circuit simplification methods;
# - symbolic circuit compilation;
# - measurement reduction for expectation value calculations.

# For the sake of completeness, the following gives the full code for the final solution, including passing the objective function to a classical optimiser to find the ground state:

import openfermion as of
from scipy.optimize import minimize
from sympy import symbols

from pytket.extensions.qiskit import AerBackend
from pytket.circuit import Circuit, Qubit
from pytket.partition import PauliPartitionStrat
from pytket.passes import GuidedPauliSimp, FullPeepholeOptimise
from pytket.pauli import Pauli, QubitPauliString
from pytket.utils import get_operator_expectation_value, gen_term_sequence_circuit
from pytket.utils.operators import QubitPauliOperator

# Obtain electronic Hamiltonian:

hamiltonian = (
    -0.8153001706270075 * of.QubitOperator("")
    + 0.16988452027940318 * of.QubitOperator("Z0")
    + -0.21886306781219608 * of.QubitOperator("Z1")
    + 0.16988452027940323 * of.QubitOperator("Z2")
    + -0.2188630678121961 * of.QubitOperator("Z3")
    + 0.12005143072546047 * of.QubitOperator("Z0 Z1")
    + 0.16821198673715723 * of.QubitOperator("Z0 Z2")
    + 0.16549431486978672 * of.QubitOperator("Z0 Z3")
    + 0.16549431486978672 * of.QubitOperator("Z1 Z2")
    + 0.1739537877649417 * of.QubitOperator("Z1 Z3")
    + 0.12005143072546047 * of.QubitOperator("Z2 Z3")
    + 0.04544288414432624 * of.QubitOperator("X0 X1 X2 X3")
    + 0.04544288414432624 * of.QubitOperator("X0 X1 Y2 Y3")
    + 0.04544288414432624 * of.QubitOperator("Y0 Y1 X2 X3")
    + 0.04544288414432624 * of.QubitOperator("Y0 Y1 Y2 Y3")
)
nuclear_repulsion_energy = 0.70556961456

pauli_sym = {"I": Pauli.I, "X": Pauli.X, "Y": Pauli.Y, "Z": Pauli.Z}


def qps_from_openfermion(paulis):
    """Convert OpenFermion tensor of Paulis to pytket QubitPauliString."""
    qlist = []
    plist = []
    for q, p in paulis:
        qlist.append(Qubit(q))
        plist.append(pauli_sym[p])
    return QubitPauliString(qlist, plist)


def qpo_from_openfermion(openf_op):
    """Convert OpenFermion QubitOperator to pytket QubitPauliOperator."""
    tk_op = dict()
    for term, coeff in openf_op.terms.items():
        string = qps_from_openfermion(term)
        tk_op[string] = coeff
    return QubitPauliOperator(tk_op)


hamiltonian_op = qpo_from_openfermion(hamiltonian)

# Obtain terms for single and double excitations:

q = [Qubit(i) for i in range(4)]
xyii = QubitPauliString([q[0], q[1]], [Pauli.X, Pauli.Y])
yxii = QubitPauliString([q[0], q[1]], [Pauli.Y, Pauli.X])
iixy = QubitPauliString([q[2], q[3]], [Pauli.X, Pauli.Y])
iiyx = QubitPauliString([q[2], q[3]], [Pauli.Y, Pauli.X])
xxxy = QubitPauliString(q, [Pauli.X, Pauli.X, Pauli.X, Pauli.Y])
xxyx = QubitPauliString(q, [Pauli.X, Pauli.X, Pauli.Y, Pauli.X])
xyxx = QubitPauliString(q, [Pauli.X, Pauli.Y, Pauli.X, Pauli.X])
yxxx = QubitPauliString(q, [Pauli.Y, Pauli.X, Pauli.X, Pauli.X])
yyyx = QubitPauliString(q, [Pauli.Y, Pauli.Y, Pauli.Y, Pauli.X])
yyxy = QubitPauliString(q, [Pauli.Y, Pauli.Y, Pauli.X, Pauli.Y])
yxyy = QubitPauliString(q, [Pauli.Y, Pauli.X, Pauli.Y, Pauli.Y])
xyyy = QubitPauliString(q, [Pauli.X, Pauli.Y, Pauli.Y, Pauli.Y])

# Symbolic UCC ansatz generation:

syms = symbols("p0 p1 p2")
singles_syms = {xyii: syms[0], yxii: -syms[0], iixy: syms[1], iiyx: -syms[1]}
doubles_syms = {
    xxxy: 0.25 * syms[2],
    xxyx: -0.25 * syms[2],
    xyxx: 0.25 * syms[2],
    yxxx: -0.25 * syms[2],
    yyyx: -0.25 * syms[2],
    yyxy: 0.25 * syms[2],
    yxyy: -0.25 * syms[2],
    xyyy: 0.25 * syms[2],
}
excitation_op = QubitPauliOperator({**singles_syms, **doubles_syms})
ucc_ref = Circuit(4).X(0).X(2)
ucc = gen_term_sequence_circuit(excitation_op, ucc_ref)

# Circuit simplification:

GuidedPauliSimp().apply(ucc)
FullPeepholeOptimise().apply(ucc)

# Connect to a simulator/device:

backend = AerBackend()

# Objective function:


def objective(params):
    circ = ucc.copy()
    sym_map = dict(zip(syms, params))
    circ.symbol_substitution(sym_map)
    return (
        get_operator_expectation_value(
            circ,
            hamiltonian_op,
            backend,
            n_shots=4000,
            partition_strat=PauliPartitionStrat.CommutingSets,
        )
        + nuclear_repulsion_energy
    ).real


# Optimise against the objective function:

initial_params = [1e-4, 1e-4, 4e-1]
# #result = minimize(objective, initial_params, method="Nelder-Mead")
# #print("Final parameter values", result.x)
# #print("Final energy value", result.fun)

# Exercises:
# - Replace the `get_operator_expectation_value` call with its implementation and use this to pull the analysis for measurement reduction outside of the objective function, so our circuits can be fully determined and compiled once. This means that the `symbol_substitution` method will need to be applied to each measurement circuit instead of just the state preparation circuit.
# - Use the `SpamCorrecter` class to add some mitigation of the measurement errors. Start by running the characterisation circuits first, before your main VQE loop, then apply the mitigation to each of the circuits run within the objective function.
# - Change the `backend` by passing in a `Qiskit` `NoiseModel` to simulate a noisy device. Compare the accuracy of the objective function both with and without the circuit simplification. Try running a classical optimiser over the objective function and compare the convergence rates with different noise models. If you have access to a QPU, try changing the `backend` to connect to that and compare the results to the simulator.
