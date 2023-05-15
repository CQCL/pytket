#!/usr/bin/env python
# coding: utf-8

# # Circuit Boxes in pytket
# 
# Quantum algorithms are often described at the level of individual logic gates. Thinking of quantum circuits in this way can have some benefits as quantum device performance is greatly influenced by low level implementation details such as gate count and circuit depth.
# 
# However quantum circuits can be challenging to interpret if expressed in terms of primitive gates only. This motivates the idea of circuit boxes which contain circuits performing higher level subroutines.

# ## CircBox

# As a minimal example lets build a circuit oracle circuit and wrap it up in a box. Our oracle will mark the `00` basis state in a superposition with a minus sign and leave the rest of the amplitudes unchanged. 

# In[1]:


from pytket.circuit import Circuit, OpType, CircBox
from pytket.circuit.display import render_circuit_jupyter

oracle_circ = Circuit(2, name='Oracle')
oracle_circ.X(0)
oracle_circ.X(1)
oracle_circ.CZ(0, 1)
oracle_circ.X(0)
oracle_circ.X(1)

render_circuit_jupyter(oracle_circ)


# In[2]:


oracle_box = CircBox(oracle_circ)


# Now that we have constructed a `CircBox` for the oracle lets append this to a circuit. We can prepare a uniform superposition of basis states with Hadamard gates before applying the oracle.

# In[3]:


circ = Circuit(2)
circ.H(0).H(1)  
circ.add_circbox(oracle_box, [0, 1])

render_circuit_jupyter(circ)


# Lets double check that our oracle `CircBox` marks the `00` bitstring as intended. We can do this by using the TKET's built in statevector simulator.

# In[4]:


circ.get_statevector()


# We see that the first amplitude of the statevector is marked with a minus sign.

# Notice how the `CircBox` inherits the name "Oracle" from the underlying circuit and the name appears in the circuit diagram. We can also inspect the underlying `Circuit` by clicking on the box in the circuit display.

# ## The Quantum Fourier Transform subroutine

# The quantum fourier transform (QFT) is a widely used subroutine in quantum computing appearing in Shor's algorithm and phase estimation based approaches to quantum chemistry.

# We can build the circuit for the $n$ qubit QFT using $n$ Hadamard gates $\frac{n}{2}$ swap gates and $\frac{n(n-1)}{2}$ controlled unitary rotations.  
# 
# $$
# \begin{equation}
# \text{CU1} = 
# \begin{pmatrix}
# I & 0 \\
# 0 & \text{U1}
# \end{pmatrix}
# \,, \quad 
# \text{U1} = 
# \begin{pmatrix}
# 1 & 0 \\
# 0 & e^{i \pi \theta}
# \end{pmatrix}
# \end{equation}
# $$
# 
# We will rotate by smaller and smaller angles of $\theta = \frac{1}{2^{n-1}}$ 

# Lets build the QFT circuit for 3 qubits.

# In[5]:


from pytket.circuit import OpType

qft_circ = Circuit(3, name="QFT")

qft_circ.H(0)
qft_circ.add_gate(OpType.CU1 , [0.5], [1, 0])
qft_circ.add_gate(OpType.CU1 , [0.25], [2, 0])

qft_circ.H(1)
qft_circ.add_gate(OpType.CU1 , [0.5], [2, 1])

qft_circ.H(2)

qft_circ.SWAP(0, 2)

render_circuit_jupyter(qft_circ)


# In[6]:


qft3_box = CircBox(qft_circ) # Define QFT box


# The inverse quantum fourier transform is also a very common subroutine. We can make a `CircBox` for doing the inverse transformation easily using `CircBox.dagger`. 

# In[7]:


qft3_inv_box = qft3_box.dagger


# We can inspect the underlying circuit for the inverse QFT with the `CircBox.get_circuit()` method.

# In[8]:


qft3_inv = qft3_inv_box.get_circuit()

render_circuit_jupyter(qft3_inv)


# In[9]:


qft3_box = CircBox(qft_circ)

circ = Circuit(3)

circ.add_circbox(qft3_box, [0, 1, 2])

render_circuit_jupyter(circ)


# ## Boxes for Unitary Synthesis
# 
# A useful feature when constructing circuits is the ability to generate a circuit to implement a given unitary transformation. This is useful when the disired unitary cannot be expressed directly as a single gate operation. 

# Unitary synthesis is supported in pytket for 1, 2 and 3 qubit unitaries using the `Unitary1qBox`, `Unitary2qBox` and `Unitary3qBox`.

# As an example lets synthesise circuits to implement the $\sqrt{Z}$ and Fermionic SWAP (FSWAP) operations which correspond to the following two unitaries.
# 
# $$
# \begin{equation}
# \sqrt{Z} = 
# \begin{pmatrix}
# 1 & 0 \\
# 0 & i \\
# \end{pmatrix}
# \, , \quad
# \text{FSWAP} =
# \begin{pmatrix}
# 1 & 0 & 0 & 0 \\
# 0 & 0 & 1 & 0 \\
# 0 & 1 & 0 & 0\\
# 0 & 0 & 0 & -1 
# \end{pmatrix}
# \end{equation}
# $$
# 
# We can simply construct a `Unitary1qBox` and `Unitary2qBox` from numpy arrays representing the desired unitary transformations.

# In[10]:


from pytket.circuit import Unitary1qBox, Unitary2qBox
import numpy as np

unitary_1q = np.asarray([
                 [1, 0],
                 [0, 1j]])

u1_box = Unitary1qBox(unitary_1q)

unitary_2q = np.asarray([
                 [1, 0, 0, 0],
                 [0, 0, 1, 0],
                 [0, 1, 0, 0],
                 [0, 0, 0, -1]])

u2_box = Unitary2qBox(unitary_2q)

test_circ = Circuit(2)
test_circ.add_unitary1qbox(u1_box, 0)
test_circ.add_unitary2qbox(u2_box, 0, 1)

render_circuit_jupyter(test_circ)


# Note here that the when adding a unitary box to a `Circuit` the box is of fixed size so we can pass our qubit indices in as separate arguments instead of using a list of qubits.

# Internally unitary boxes expressses the unitary operation in terms of gates supported by pytket. We can view the underlying circuirt with the `CircBox.get_circuit()` method or by applying the `DecomposeBoxes` compilation pass.

# In[11]:


render_circuit_jupyter(u2_box.get_circuit())


# Synthesising a circuit for a general unitary is only supported in pytket for up to 3 qubits. This is because unitary synthesis scales exponentially with respect to both runtime and circuit complexity.
# 
# The `DiagonalBox` allows the user to synthesise circuits for diagonal unitaries with more than 3 qubits. Here the `DiagonalBox` can be constructed using a numpy array of the diagonal elements rather than the entire unitary.
# 
# As an example let's synthesise a circuit for the following 4 qubit diagonal unitary.
# 
# $$
# \begin{equation}
# U_{4q} = \text{diag}(1, i, 1, i, 1, i, 1, i, 1, i, 1, i, 1, i, 1, i)
# \end{equation}
# $$

# In[12]:


from pytket.circuit import Qubit, DiagonalBox

diagonal_4q = [1, 1j] * 8
diag_box = DiagonalBox(diagonal_4q)

circ_4q = Circuit(4)
qubits = [Qubit(i) for i in range(circ_4q.n_qubits)]
circ_4q.add_diagonal_box(diag_box, qubits)
                         

render_circuit_jupyter(circ_4q)


# The `DiagonalBox` will be constructed using a sequence of `Mutliplexor` operations - more on these later.

# ## Controlled Unitary Operations with `QControlBox`

# TKET also supports the use of "Controlled-U" operations where U is some unitary box defined by the user.
# 
# This can be done by defining a `QControlBox`. These controlled operations can be made from a `CircBox` or any other box type in TKET that doesn't contain classical operations.

# Lets define a multicontrolled $\sqrt{Z}$ gate using the `Unitary1qBox` that we defined above.

# In[13]:


from pytket.circuit import QControlBox

test_circ2 = Circuit(3)

# sqrt(Z) gate controlled on two qubits 
c2_rootz = QControlBox(u1_box, n=2)

test_circ2.add_qcontrolbox(c2_rootz, [0, 1, 2])

render_circuit_jupyter(test_circ2)


# ## Pauli Exponentials 

# Exponentiated Pauli operators appear in many applications of quantum computing. 
# 
# Pauli exponentials are defined in terms of a Pauli string $P$ and a phase $\theta$ and are written in the following form
# 
# $$
# \begin{equation}
# U_P = e^{i \frac{\pi}{2}\theta P}\,, \quad \theta \in \mathbb{R}, \,\,P \in \{I,\, X,\, Y,\, Z \}
# \end{equation}
# $$
# 
# 
# Pauli strings are tensor products of the Pauli matrices $\{I,\, X,\, Y,\, Z \}$
# 
# 
# $$
# \begin{equation}
# XYYZ \equiv X \otimes Y \otimes Y \otimes Z
# \end{equation}
# $$
# 
# Consider the following two Pauli Exponentials
# 
# $$
# \begin{equation}
# U_{XYYZ} = e^{-i \frac{\pi}{2}\theta XYYZ}\,, \quad U_{ZZYX} = e^{-i \frac{\pi}{2}\theta ZZYX}
# \end{equation}
# $$
# 
# We can implement these two Pauli exponetials using the `PauliExpBox` in pytket. To construct a `PauliExpBox` we have to pass in a list of pauli operators and a phase which represents $\theta$ in the equations above. 

# In[14]:


from pytket.circuit import PauliExpBox
from pytket.pauli import Pauli

# Construct PauliExpBox(es) with a list of Paulis followed by the phase
xyyz = PauliExpBox([Pauli.X, Pauli.Y, Pauli.Y, Pauli.Z], -0.2)
zzyx = PauliExpBox([Pauli.Z, Pauli.Z, Pauli.Y, Pauli.X], 0.7)

pauli_circ = Circuit(5)

pauli_circ.add_pauliexpbox(xyyz, [0, 1, 2, 3])
pauli_circ.add_pauliexpbox(zzyx, [1, 2, 3, 4])

render_circuit_jupyter(pauli_circ)


# To understand what happens inside a `PauliExpBox` lets take a look at the underlying circuit for $e^{-i \frac{\pi}{2}\theta ZZYX}$.

# In[15]:


render_circuit_jupyter(zzyx.get_circuit())


# All Pauli Exponetials of the form above can be implemented in terms of a single Rz($\theta$) rotation and a symmetric chain of CX gates on either side together with some single qubit basis rotations. This class of circuit is called a Pauli Gadget. The subset of these circuits corresponding to "Z only" Pauli strings are referred to as phase gadgets.
# 
# We see that the Pauli exponential $e^{i\theta \text{ZZYX}}$ has basis rotations on the third and fourth qubit. The V and Vdg gates rotate from the default Z basis to the Y basis and the Hadamard gate serves to change to the X basis.
# 
# These Pauli gadget circuits have interesting algebraic properties which are useful for circuit optimisation. For further discussion see the research publication on phase gadget synthesis ( 	arXiv:1906.01734). Ideas from this paper are implemented in TKET as the `OptimisePhaseGadgets` and `PauliSimp` optimisation passes.

# ## Phase Polynomials

# Phase polynomial circuits are a special class of circuits that use the {CX, Rz} gateset.
# 
# A phase polynomial $p(x)$ is defined as as a linear combination of Boolean linear functions $f_i(x)$
# 
# $$
# \begin{equation}
# p(x) = \sum_{i=1}^{2^n} \theta_i f_i(x)
# \end{equation}
# $$
# A phase polynomial circuit is a circuit which has the following action on computational basis states $|x\rangle$
# $$
# \begin{equation}
# |x\rangle \longmapsto e^{2\pi i p(x)}|g(x)\rangle
# \end{equation}
# $$
# 
# A phase polynomial circuit can be synthesisied in pytket using the `PhasePolyBox`. The `PhasePolyBox` is constructed using the number of qubits, qubit indices as well as a dictionary indicating whether or not a phase should be applied to specific qubits.
# 
# Finally a `linear_transfromation` parameter needs to be specified  which is a matrix encoding the linear permutation between the bitsrings $|x\rangle$ and $|g(x)\rangle$ in the equation above.

# In[17]:


from pytket.circuit import PhasePolyBox

phase_poly_circ = Circuit(3)

qubit_indices = {Qubit(0): 0, Qubit(1): 1, Qubit(2): 2}

phase_polynomial = {
        (True, False, True): 0.333,
        (False, False, True): 0.05,
        (False, True, False): 1.05,}

n_qb = 3

linear_transformation = np.array([[1, 1, 0], [0, 1, 0], [0, 0, 1]])

p_box = PhasePolyBox(n_qb,
                     qubit_indices,
                     phase_polynomial,
                     linear_transformation)

phase_poly_circ.add_phasepolybox(p_box, [0, 1, 2])

render_circuit_jupyter(p_box.get_circuit())


# ## Multiplexors, State Preperation and ToffoliBox

# In the context of quantum circuits a multiplexor is type of generalised multicontrolled gate. Multiplexors grant us the flexibilty to specify different operations on target qubits for different control states.
# 
# To create a multiplexor we simply construct a dictionary where the keys are the state of the control qubits and the values represent the operation perfomed on the target.
# 
# Lets implement a multiplexor with the following logic. Here we treat the first two qubits a controls and the third qubit as the target.
# 
# ```
# if control qubits in |00>:
#     do Rz(0.3) on third qubit
# else if control qubits in |11>:
#      do H on third qubit
# else:
#     do identity (i.e. do nothing)
# ```

# In[18]:


from pytket.circuit import Op, MultiplexorBox

# Define both gates as an Op
rz_op = Op.create(OpType.Rz, 0.3)
h_op = Op.create(OpType.H)

op_map = {(0, 0): rz_op, (1, 1): h_op}
multiplexor = MultiplexorBox(op_map)


# In[19]:


# Assume all qubits initialised to |0> here
multi_circ = Circuit(3)
multi_circ.X(0).X(1) # Put both control qubits in the state |1>
multi_circ.add_multiplexor(multiplexor, [Qubit(0), Qubit(1), Qubit(2)])

render_circuit_jupyter(multi_circ)


# Notice how in the example above the control qubits are both in the $|1\rangle$ state and so the multiplexor applies the Hadamard operation to the third qubit. If we calculate our statevector we see that the third qubit is in the $|+\rangle = H|0\rangle$ state.

# In[20]:


print("Statevector =", multi_circ.get_statevector()) # amplitudes of |+> approx 0.707...


# One place where multiplexor operations are useful is in state preperation algorithms. 
# 
# TKET supports the preperation of arbitrary quantum states via the `StatePreparationBox`. This box takes a $ (1\times 2^n)$ numpy array representing the $n$ qubit statevector where the entries represent the amplitudes of the quantum state.
# 
# Given the vector of amplitudes TKET will construct a box containing a sequence of multiplexors using the method outlined in (arXiv:quant-ph/0406176).
# 
# Note that generic state preperation circuits can be very complex with the gatecount and depth increasing rapidly with the size of the state. In the special case where the desired state has only real valued amplitudes only multiplexed Ry operations are needed to accomplish the state prepartion.   

# $$
# \begin{equation}
# |W\rangle = \frac{1}{\sqrt{3}} \big(|001\rangle + |010\rangle + |100\rangle
# \end{equation}
# $$

# In[21]:


werner_state = 1 / np.sqrt(3) * np.array([0, 1, 1, 0, 1, 0, 0, 0])


# In[23]:


from pytket.circuit import StatePreparationBox

prob_state_box = StatePreparationBox(werner_state)

state_circ = Circuit(3)
state_circ.add_state_preparation_box(prob_state_box, [Qubit(0), Qubit(1), Qubit(2)])
render_circuit_jupyter(state_circ)


# In[24]:


# Verify state preperation
np.round(state_circ.get_statevector().real, 3) 


# Finally lets consider another box type namely the `ToffoliBox`. This box can be used to prepare an arbitary permutation of the computational basis states.
# 
# To construct the box we need to specify the permuation as a key:value pair where the key is the input basis state and the value is output. 
# 
# Lets construct a `ToffoliBox` to perform the following mapping
# 
# $$
# \begin{equation}
# |001\rangle \longmapsto |111\rangle \\
# |111\rangle \longmapsto |001\rangle \\
# |100\rangle \longmapsto |000\rangle \\
# |000\rangle \longmapsto |100\rangle
# \end{equation}
# $$
# 
# For correctness if a basis state appears as key in the permutation dictionary then it must also appear and a value.

# In[26]:


from pytket.circuit import ToffoliBox

# Specify the desired permutation of the basis states
mapping = {(0, 0, 1): (1, 1, 1), (1, 1, 1): (0, 0, 1),
           (1, 0, 0): (0, 0, 0), (0, 0, 0):(1, 0, 0)}

# Define box to perform the permutation
perm_box = ToffoliBox(permutation=mapping)


# The permutation is implemented using a sequence of multiplexed rotations followed by a `DiagonalBox`.

# In[27]:


render_circuit_jupyter(perm_box.get_circuit())


# Finally lets append the `ToffoliBox` onto our circuit preparing our Werner state to perfom the permutation of basis states specifed above.

# In[30]:


state_circ.add_toffolibox(perm_box, [0, 1, 2]) 
render_circuit_jupyter(state_circ)


# In[29]:


np.round(state_circ.get_statevector().real, 3) 


# Looking at the statevector calculation we see that our `ToffoliBox` has exchanged the coefficents of our Werner state so that the non-zero coefficents are now on the `000` and `111` bitstrings with the coefficent of `010` remaining unchanged.
