# # Conditional gates

# Whilst any quantum process can be created by performing "pure" operations delaying all measurements to the end, this is not always practical and can greatly increase the resource requirements. It is much more convenient to alternate quantum gates and measurements, especially if we can use the measurement results to determine which gates to apply (we refer to this more generic circuit model as "mixed" circuits, against the usual "pure" circuits). This is especially crucial for error correcting codes, where the correction gates are applied only if an error is detected.
#
# Measurements on many NISQ devices are often slow and it is hard to maintain other qubits in a quantum state during the measurement operation. Hence they may only support a single round of measurements at the end of the circuit, removing the need for conditional gate support. However, the ability to work with mid-circuit measurement and conditional gates is a feature in high demand for the future, and tket is ready for it.
#
# Not every circuit language specification supports conditional gates in the same way. The most popular circuit model at the moment is that provided by the OpenQASM language. This permits a very restricted model of classical logic, where we can apply a gate conditionally on the exact value of a classical register. There is no facility in the current spec for Boolean logic or classical operations to apply any function to the value prior to the equality check.
#
# For example, quantum teleportation can be performed by the following QASM:
# `OPENQASM 2.0;`
# `include "qelib1.inc";`
# `qreg a[2];`
# `qreg b[1];`
# `creg c[2];`
# `// Bell state between Alice and Bob`
# `h a[1];`
# `cx a[1],b[0];`
# `// Bell measurement of Alice's qubits`
# `cx a[0],a[1];`
# `h a[0];`
# `measure a[0] -> c[0];`
# `measure a[1] -> c[1];`
# `// Correction of Bob's qubit`
# `if(c==1) z b[0];`
# `if(c==3) z b[0];`
# `if(c==2) x b[0];`
# `if(c==3) x b[0];`

# tket supports a slightly more general form of conditional gates, where the gate is applied conditionally on the exact value of any list of bits. When adding a gate to a `Circuit` object, pass in the kwargs `condition_bits` and `condition_value` and the gate will only be applied if the state of the bits yields the binary representation of the value.

from pytket import Circuit
from pytket.circuit.display import render_circuit_jupyter

circ = Circuit()
alice = circ.add_q_register("a", 2)
bob = circ.add_q_register("b", 1)
cr = circ.add_c_register("c", 2)
# Bell state between Alice and Bob:
circ.H(alice[1])
circ.CX(alice[1], bob[0])
# Bell measurement of Alice's qubits:
circ.CX(alice[0], alice[1])
circ.H(alice[0])
circ.Measure(alice[0], cr[0])
circ.Measure(alice[1], cr[1])
# Correction of Bob's qubit:
circ.Z(bob[0], condition_bits=[cr[0]], condition_value=1)
circ.X(bob[0], condition_bits=[cr[1]], condition_value=1)
render_circuit_jupyter(circ)


# Performing individual gates conditionally is sufficient, but can get cumbersome for larger circuits. Fortunately, tket's Box structures can also be performed conditionally, enabling this to be applied to large circuits with ease.
#
# For the sake of example, assume our device struggles to perform $X$ gates. We can surround it by $CX$ gates onto an ancilla, so measuring the ancilla will either result in the identity or $X$ being applied to the target qubit. If we detect that the $X$ fails, we can retry.

from pytket.circuit import CircBox, Qubit, Bit

checked_x = Circuit(2, 1)
checked_x.CX(0, 1)
checked_x.X(0)
checked_x.CX(0, 1)
checked_x.Measure(1, 0)
x_box = CircBox(checked_x)

circ2 = Circuit()
target = Qubit("t", 0)
ancilla = Qubit("a", 0)
success = Bit("s", 0)
circ2.add_qubit(target)
circ2.add_qubit(ancilla)
circ2.add_bit(success)

# Try the X gate:

circ2.add_gate(x_box, args=[target, ancilla, success])
# Try again if the X failed
circ2.add_gate(
    x_box, args=[target, ancilla, success], condition_bits=[success], condition_value=0
)
render_circuit_jupyter(circ2)

# tket is able to apply essential compilation passes on circuits containing conditional gates. This includes decomposing any boxes into primitive gates and rebasing to other gatesets whilst preserving the conditional data.

from pytket.passes import DecomposeBoxes, RebaseTket, SequencePass

comp_pass = SequencePass([DecomposeBoxes(), RebaseTket()])
comp_pass.apply(circ2)
render_circuit_jupyter(circ2)


# A tket circuit can be converted to OpenQASM or other languages following the same classical model (e.g. Qiskit) when all conditional gates are dependent on the exact state of a single, whole classical register.

from pytket.extensions.qiskit import tk_to_qiskit

qc = tk_to_qiskit(circ2)
print(qc)

# This allows us to test our mixed programs using the `AerBackend`.

from pytket.extensions.qiskit import AerBackend

circ3 = Circuit(2, 1)
circ3.Rx(0.3, 0)
circ3.Measure(0, 0)
# Set qubit 1 to be the opposite result and measure
circ3.X(1, condition_bits=[0], condition_value=0)
circ3.Measure(1, 0)
backend = AerBackend()
compiled_circ = backend.get_compiled_circuit(circ3)
render_circuit_jupyter(compiled_circ)

counts = backend.run_circuit(compiled_circ, 1024).get_counts()
print(counts)

# Try out mid-circuit measurement and conditional gate support on the `AerBackend` simulator, or ask about accessing the `QuantinuumBackend` to try on a hardware device.
