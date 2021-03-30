# # Ansatz Sequencing: tket example
#
# When performing variational algorithms like VQE, one common approach to generating circuit ansätze is to take an operator $U$ representing excitations and use this to act on a reference state $\lvert \phi_0 \rangle$. One such ansatz is the Unitary Coupled Cluster ansatz. Each excitation, indexed by $j$, within $U$ is given a real coefficient $a_j$ and a parameter $t_j$, such that $U = e^{i \sum_j \sum_k a_j t_j P_{jk}}$, where $P_{jk} \in \{I, X, Y, Z \}^{\otimes n}$. The exact form is dependent on the chosen qubit encoding. This excitation gives us a variational state $\lvert \psi (t) \rangle = U(t) \lvert \phi_0 \rangle$. The operator $U$ must be Trotterised, to give a product of Pauli exponentials, and converted into native quantum gates to create the ansatz circuit.
#
# This notebook will describe how to use an advanced feature of `pytket` to enable automated circuit synthesis for $U$ and reduce circuit depth dramatically.
#
# We must create a `pytket` `QubitPauliOperator`, which represents such an operator $U$, and contains a dictionary from Pauli string $P_{jk}$ to symbolic expression. Here, we make a mock operator ourselves, which resembles the UCCSD excitation operator for the $\mathrm{H}_2$ molecule using the Jordan-Wigner qubit encoding. In the future, operator generation will be handled automatically using CQC's upcoming software for enterprise quantum chemistry, EUMEN. We also offer conversion to and from the `OpenFermion` `QubitOperator` class, although at the time of writing a `QubitOperator` cannot handle arbitrary symbols.
#
# First, we create a series of `QubitPauliString` objects, which represent each $P_{jk}$.

from pytket.pauli import Pauli, QubitPauliString
from pytket.circuit import Qubit

q = [Qubit(i) for i in range(4)]
qps0 = QubitPauliString([q[0], q[1], q[2]], [Pauli.Y, Pauli.Z, Pauli.X])
qps1 = QubitPauliString([q[0], q[1], q[2]], [Pauli.X, Pauli.Z, Pauli.Y])
qps2 = QubitPauliString(q, [Pauli.X, Pauli.X, Pauli.X, Pauli.Y])
qps3 = QubitPauliString(q, [Pauli.X, Pauli.X, Pauli.Y, Pauli.X])
qps4 = QubitPauliString(q, [Pauli.X, Pauli.Y, Pauli.X, Pauli.X])
qps5 = QubitPauliString(q, [Pauli.Y, Pauli.X, Pauli.X, Pauli.X])

# Now, create some symbolic expressions for the $a_j t_j$ terms.

from pytket.circuit import fresh_symbol

symbol1 = fresh_symbol("s0")
expr1 = 1.2 * symbol1
symbol2 = fresh_symbol("s1")
expr2 = -0.3 * symbol2

# We can now create our `QubitPauliOperator`.

from pytket.utils import QubitPauliOperator

dict1 = dict((string, expr1) for string in (qps0, qps1))
dict2 = dict((string, expr2) for string in (qps2, qps3, qps4, qps5))
operator = QubitPauliOperator({**dict1, **dict2})
print(operator)

# Now we can let `pytket` sequence the terms in this operator for us, using a selection of strategies. First, we will create a `Circuit` to generate an example reference state, and then use the `gen_term_sequence_circuit` method to append the Pauli exponentials.

from pytket.circuit import Circuit
from pytket.utils import gen_term_sequence_circuit
from pytket.partition import PauliPartitionStrat, GraphColourMethod

reference_circ = Circuit(4).X(1).X(3)
ansatz_circuit = gen_term_sequence_circuit(
    operator, reference_circ, PauliPartitionStrat.CommutingSets, GraphColourMethod.Lazy
)

# This method works by generating a graph of Pauli exponentials and performing graph colouring. Here we have chosen to partition the terms so that exponentials which commute are gathered together, and we have done so using a lazy, greedy graph colouring method.
#
# Alternatively, we could have used the `PauliPartitionStrat.NonConflictingSets`, which puts Pauli exponentials together so that they only require single-qubit gates to be converted into the form $e^{i \alpha Z \otimes Z \otimes ... \otimes Z}$. This strategy is primarily useful for measurement reduction, a different problem.
#
# We could also have used the `GraphColourMethod.LargestFirst`, which still uses a greedy method, but builds the full graph and iterates through the vertices in descending order of arity. We recommend playing around with the options, but we typically find that the combination of `CommutingSets` and `Lazy` allows the best optimisation.
#
# In general, not all of our exponentials will commute, so the semantics of our circuit depend on the order of our sequencing. As a result, it is important for us to be able to inspect the order we have produced. `pytket` provides functionality to enable this. Each set of commuting exponentials is put into a `CircBox`, which lets us inspect the partitoning.

from pytket.circuit import OpType

for command in ansatz_circuit:
    if command.op.type == OpType.CircBox:
        print("New CircBox:")
        for pauli_exp in command.op.get_circuit():
            print(
                " {} {} {}".format(
                    pauli_exp, pauli_exp.op.get_paulis(), pauli_exp.op.get_phase()
                )
            )
    else:
        print("Native gate: {}".format(command))

# We can convert this circuit into basic gates using a `pytket` `Transform`. This acts in place on the circuit to do rewriting, for gate translation and optimisation. We will start off with a naive decomposition.

from pytket.transform import Transform

naive_circuit = ansatz_circuit.copy()
Transform.DecomposeBoxes().apply(naive_circuit)
print(naive_circuit.get_commands())

# This is a jumble of one- and two-qubit gates. We can get some relevant circuit metrics out:

print("Naive CX Depth: {}".format(naive_circuit.depth_by_type(OpType.CX)))
print("Naive CX Count: {}".format(naive_circuit.n_gates_of_type(OpType.CX)))

# These metrics can be improved upon significantly by smart compilation. A `Transform` exists precisely for this purpose:

from pytket.transform import PauliSynthStrat, CXConfigType

smart_circuit = ansatz_circuit.copy()
Transform.UCCSynthesis(PauliSynthStrat.Sets, CXConfigType.Tree).apply(smart_circuit)
print("Smart CX Depth: {}".format(smart_circuit.depth_by_type(OpType.CX)))
print("Smart CX Count: {}".format(smart_circuit.n_gates_of_type(OpType.CX)))

# This `Transform` takes in a `Circuit` with the structure specified above: some arbitrary gates for the reference state, along with several `CircBox` gates containing `PauliExpBox` gates.
#
# We have chosen `PauliSynthStrat.Sets` and `CXConfigType.Tree`. The `PauliSynthStrat` dictates the method for decomposing multiple adjacent Pauli exponentials into basic gates, while the `CXConfigType` dictates the structure of adjacent CX gates.
#
# If we choose a different combination of strategies, we can produce a different output circuit:

last_circuit = ansatz_circuit.copy()
Transform.UCCSynthesis(PauliSynthStrat.Individual, CXConfigType.Snake).apply(
    last_circuit
)
print(last_circuit.get_commands())

print("Last CX Depth: {}".format(last_circuit.depth_by_type(OpType.CX)))
print("Last CX Count: {}".format(last_circuit.n_gates_of_type(OpType.CX)))

# Other than some single-qubit Cliffords we acquired via synthesis, you can check that this gives us the same circuit structure as our `Transform.DecomposeBoxes` method! It is a suboptimal synthesis method.
#
# As with the `gen_term_sequence` method, we recommend playing around with the arguments and seeing what circuits come out. Typically we find that `PauliSynthStrat.Sets` and `CXConfigType.Tree` work the best, although routing can affect this somewhat.
