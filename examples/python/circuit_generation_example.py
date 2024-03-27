# # Circuit generation

# This notebook will provide a brief introduction to some of the more advanced methods of circuit generation available in `pytket`, including:
# * how to address wires and registers;
# * reading in circuits from QASM and Quipper ASCII files;
# * various types of 'boxes';
# * composition of circuits (both 'horizontally' and 'vertically');
# * use of symbolic gate parameters;
# * representation of classically controlled gates.

# ## Wires, unit IDs and registers

# Let's get started by constructing a circuit with 3 qubits and 2 classical bits:

from pytket.circuit import Circuit

c = Circuit(3, 2)
print(c.qubits)
print(c.bits)

# The qubits have automatically been assigned to a register with name `q` and indices 0, 1 and 2, while the bits have been assigned to a register with name `c` and indices 0 and 1.
#
# We can give these units arbitrary names and indices of arbitrary dimension:

from pytket.circuit import Qubit

new_q1 = Qubit("alpha", 0)
new_q2 = Qubit("beta", 2, 1)
new_q3 = Qubit("gamma", (0, 0, 0))
c.add_qubit(new_q1)
c.add_qubit(new_q2)
c.add_qubit(new_q3)
print(c.qubits)

# We can also add a new register of qubits in one go:

c.add_q_register("delta", 4)
print(c.qubits)

# Similar commands are available for classical bits.
#
# We can add gates to the circuit as follows:

c.CX(0, 1)

# This command appends a CX gate with control `q[0]` and target `q[1]`. Note that the integer arguments are automatically converted to the default unit IDs. For simple circuits it is often easiest to stick to the default register and refer to the qubits by integers. To add gates to our own named units, we simply pass the `Qubit` (or classical `Bit`) as an argument. (We can't mix the two conventions in one command, however.)

c.H(new_q1)
c.CX(Qubit("q", 1), new_q2)
c.Rz(0.5, new_q2)
print(c.get_commands())

# Let's have a look at our circuit:

print(c.get_commands())

# ## Exporting to and importing from standard formats

# We can export a `Circuit` to a file in QASM format. Conversely, if we have such a file we can import it into `pytket`. There are some limitations on the circuits that can be converted: for example, multi-dimensional indices (as in `beta` and `gamma` above) are not allowed.
#
# Here is a simple example:

from pytket.qasm import circuit_from_qasm, circuit_to_qasm

c = Circuit(3, 1)
c.H(0)
c.CX(0, 1)
c.CX(1, 2)
c.Rz(0.25, 2)
c.Measure(2, 0)

qasmfile = "c.qasm"
circuit_to_qasm(c, qasmfile)

with open(qasmfile) as f:
    print(f.read())

c1 = circuit_from_qasm(qasmfile)
c == c1

# We can also import files in the Quipper ASCII format:

from pytket.quipper import circuit_from_quipper

quipfile = "c.quip"
with open(quipfile, "w") as f:
    f.write(
        """Inputs: 0:Qbit, 1:Qbit
QGate["W"](0,1)
QGate["omega"](1)
QGate["swap"](0,1)
QGate["W"]*(1,0)
Outputs: 0:Qbit, 1:Qbit
"""
    )

c = circuit_from_quipper(quipfile)
print(c.get_commands())

# Note that the Quipper gates that are not supported directly in `pytket` (`W` and `omega`) are translated into equivalent sequences of `pytket` gates.
#
# Quipper subroutines are also supported, corresponding to `CircBox` operations in `pytket`:

with open(quipfile, "w") as f:
    f.write(
        """Inputs: 0:Qbit, 1:Qbit, 2:Qbit
QGate["H"](0)
Subroutine(x2)["sub", shape "([Q,Q],())"] (2,1) -> (2,1)
QGate["H"](1)
Outputs: 0:Qbit, 1:Qbit, 2:Qbit \n
Subroutine: "sub"
Shape: "([Q,Q],())"
Controllable: no
Inputs: 0:Qbit, 1:Qbit
QGate["Y"](0)
QGate["not"](1) with controls=[+0]
QGate["Z"](1)
Outputs: 0:Qbit, 1:Qbit
"""
    )

c = circuit_from_quipper(quipfile)
cmds = c.get_commands()
print(cmds)

# ## Boxes

# The `CircBox` is an example of a `pytket` 'box', which is a reusable encapsulation of a circuit inside another. We can recover the circuit 'inside' the box using the `get_circuit()` method:

boxed_circuit = cmds[1].op.get_circuit()
print(boxed_circuit.get_commands())

# The `CircBox` is the most general type of box, implementing an arbitrary circuit. But `pytket` supports several other useful box types:
# * `Unitary1qBox` (implementing an arbitrary $2 \times 2$ unitary matrix);
# * `Unitary2qBox` (implementing an arbitrary $4 \times 4$ unitary matrix);
# * `ExpBox` (implementing $e^{itA}$ for an arbitrary $4 \times 4$ hermitian matrix $A$ and parameter $t$);
# * `PauliExpBox` (implementing $e^{-\frac{1}{2} i \pi t (\sigma_0 \otimes \sigma_1 \otimes \cdots)}$ for arbitrary Pauli operators $\sigma_i \in \{\mathrm{I}, \mathrm{X}, \mathrm{Y}, \mathrm{Z}\}$ and parameter $t$).

# An example will illustrate how these various box types are added to a circuit:

from math import sqrt

import numpy as np
from pytket.circuit import CircBox, ExpBox, PauliExpBox, Unitary1qBox, Unitary2qBox
from pytket.pauli import Pauli

boxycirc = Circuit(3)

# Add a `CircBox`:

subcirc = Circuit(2)
subcirc.X(0).Y(1).CZ(0, 1)
cbox = CircBox(subcirc)
boxycirc.add_gate(cbox, args=[Qubit(0), Qubit(1)])

# Add a `Unitary1qBox`:

m1 = np.asarray([[1 / 2, sqrt(3) / 2], [sqrt(3) / 2, -1 / 2]])
m1box = Unitary1qBox(m1)
boxycirc.add_gate(m1box, 2)

# Add a `Unitary2qBox`:

m2 = np.asarray([[0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1], [1, 0, 0, 0]])
m2box = Unitary2qBox(m2)
boxycirc.add_gate(m2box, 1, 2)

# Add an `ExpBox`:

A = np.asarray(
    [[1, 2, 3, 4 + 1j], [2, 0, 1j, -1], [3, -1j, 2, 1j], [4 - 1j, -1, -1j, 1]]
)
ebox = ExpBox(A, 0.5)
boxycirc.add_expbox(ebox, 0, 1)

# Add a `PauliExpBox`:

pbox = PauliExpBox([Pauli.X, Pauli.Z, Pauli.X], 0.75)
boxycirc.add_gate(pbox, [0, 1, 2])

print(boxycirc.get_commands())

# The `get_circuit()` method is available for all box types, and returns a `Circuit` object. For example:

print(pbox.get_circuit().get_commands())

# ## Circuit composition

# Circuits can be composed either serially, whereby wires are joined together, or in parallel, using the `append()` command.
#
# For a simple illustration of serial composition, let's create two circuits with compatible set of wires, and append the second to the first:

c = Circuit(2)
c.CX(0, 1)

c1 = Circuit(2)
c1.CZ(1, 0)

c.append(c1)

print(c.get_commands())

# In the above example, there was a one-to-one match between the unit IDs in the two circuits, and they were matched up accordingly. The same applied with named unit IDs:

x, y = Qubit("x"), Qubit("y")

c = Circuit()
c.add_qubit(x)
c.add_qubit(y)
c.CX(x, y)

c1 = Circuit()
c1.add_qubit(x)
c1.add_qubit(y)
c1.CZ(y, x)

c.append(c1)

print(c.get_commands())

# If either circuit contains wires not matching any wires in the other, those are added to the other circuit before composition:

z = Qubit("z")
c1.add_qubit(z)
c1.CY(y, z)
c.append(c1)
print(c.qubits)
print(c.get_commands())

# If the sets of unit IDs for the two circuits are disjoint, then the composition is entirely parallel.
#
# What if we want to serially compose two circuits having different sets of `Qubit`? In that case, we can use the `rename_units()` method on one or other of them to bring them into line. This method takes a dictionary mapping current unit IDs to new one:

c2 = Circuit()
c2.add_q_register("w", 3)
w = [Qubit("w", i) for i in range(3)]
c2.H(w[0]).CX(w[0], w[1]).CRz(0.25, w[1], w[2])

c.rename_units({x: w[0], y: w[1], z: w[2]})

c.append(c2)

print(c.get_commands())

# ## Symbolic parameters

# Many of the gates supported by `pytket` are parametrized by one or more phase parameters, which represent rotations in multiples of $\pi$. For example, $\mathrm{Rz}(\frac{1}{2})$ represents a quarter turn, i.e. a rotation of $\pi/2$, about the Z axis. If we know the values of these parameters we can add the gates directly to our circuit:

c = Circuit(1)
c.Rz(0.5, 0)

# However, we may wish to construct and manipulate circuits containing such parametrized gates without specifying the values. This allows us to do calculations in a general setting, only later substituting values for the parameters.
#
# Thus `pytket` allows us to specify any of the parameters as symbols. All manipulations (such as combination and cancellation of gates) are performed on the symbolic representation:

from sympy import Symbol

a = Symbol("a")
c.Rz(a, 0)

print(c.get_commands())

# When we apply any transformation to this circuit, the symbolic parameter is preserved in the result:

from pytket.transform import Transform

Transform.RemoveRedundancies().apply(c)

print(c.get_commands())

# To substitute values for symbols, we use the `symbol_substitution()` method, supplying a dictionary from symbols to values:

c.symbol_substitution({a: 0.75})

print(c.get_commands())

# We can also substitute symbols for other symbols:

b = Symbol("b")
c = Circuit(1)
c.Rz(a + b, 0)
c.symbol_substitution({b: 2 * a})
print(c.get_commands())

# ## Custom gates

# We can define custom parametrized gates in `pytket` by first setting up a circuit containing symbolic parameters and then converting this to a parametrized operation type:

from pytket.circuit import CustomGateDef

a = Symbol("a")
b = Symbol("b")
setup = Circuit(3)
setup.CX(0, 1)
setup.Rz(a + 0.5, 2)
setup.CRz(b, 0, 2)
my_gate = CustomGateDef.define("g", setup, [a, b])
c = Circuit(4)
c.add_custom_gate(my_gate, [0.2, 1.3], [0, 3, 1])
print(c.get_commands())

# Custom gates can also receive symbolic parameters:

x = Symbol("x")
c.add_custom_gate(my_gate, [x, 1.0], [0, 1, 2])
print(c.get_commands())

# ## Decomposing boxes and custom gates

# Having defined a circuit containing custom gates, we may now want to decompose it into elementary gates. The `DecomposeBoxes()` transform allows us to do this:

Transform.DecomposeBoxes().apply(c)
print(c.get_commands())

# The same transform works on circuits composed of arbitrary boxes. Let's try it on a copy of the circuit we built up earlier out of various box types.

c = boxycirc.copy()
Transform.DecomposeBoxes().apply(c)
print(c.get_commands())

# Note that the unitaries have been decomposed into elementary gates.

# ## Classical controls

# Most of the examples above involve only pure quantum gates. However, `pytket` can also represent gates whose operation is conditional on one or more classical inputs.
#
# For example, suppose we want to run the complex circuit `c` we've just constructed, then measure qubits 0 and 1, and finally apply an $\mathrm{Rz}(\frac{1}{2})$ rotation to qubit 2 if and only if the measurements were 0 and 1 respectively.
#
# First, we'll add two classical wires to the circuit to store the measurement results:

from pytket.circuit import Bit

c.add_c_register("m", 2)
m = [Bit("m", i) for i in range(2)]

# Classically conditioned operations depend on all their inputs being 1. Since we want to condition on `m[0]` being 0, we must first apply an X gate to its qubit, and then measure:

q = [Qubit("q", i) for i in range(3)]
c.X(q[0])
c.Measure(q[0], m[0])
c.Measure(q[1], m[1])

# Finally we add the classically conditioned Rz operation, using the `add_gate()` method:

from pytket.circuit import OpType

c.add_gate(OpType.Rz, [0.5], [q[2]], condition_bits=[m[0], m[1]], condition_value=3)

# Note that many of the transforms and compilation passes will not accept circuits that contain classical controls.
