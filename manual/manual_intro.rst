*************
What is tket?
*************

.. Two-sentence overview

The tket framework is a software platform for the development and execution of gate-level quantum computation, providing state-of-the-art performance in circuit compilation. The toolset is designed to aid platform-agnostic software and extract the most out of the available NISQ devices of today.

There is currently an implementation of tket available in the form of the ``pytket`` package for python 3.10+, which can be installed for free using the ``pip`` package manager. Additional extension modules are available for interfacing ``pytket`` with several popular quantum software packages, including `Qiskit <https://qiskit.org/>`_, `Cirq <https://quantumai.google/cirq/>`_, and `pyQuil <https://pyquil-docs.rigetti.com/en/stable/>`_, and for adding more devices and simulators to target.

.. Introduction to manual and link to other resource

This user manual is targeted at readers who are already familiar with the basics of quantum computing via the circuit model and want to explore the tools available in tket. It provides a comprehensive, feature-focussed tour of the platform to take you from "Hello world" to playing with advanced techniques for speeding up and improving the accuracy of your quantum experiments.

In addition to this manual, there is also a selection of `example notebooks <https://tket.quantinuum.com/examples>`_ to see ``pytket`` in the context of the algorithms and applications that can be built on top of it. These are supported by the API reference for in-depth overviews of each method, class, and interface.

NISQ Considerations
-------------------

.. Hardware limitations

Looking at any quantum computing textbook would give hope that quantum computers could achieve monumental goals in computation like factoring large numbers for breaking RSA-encryption, simulating molecular energies for material discovery, or speeding up unstructured searches and optimisation problems. So you would be forgiven for being excited by the availability of quantum devices and wanting to run your first instance of Grover's algorithm on real quantum hardware. The truth is that the devices of today are still some way off from having the capability to run these kinds of algorithms at an interesting scale.

.. NISQ considerations

The NISQ [Pres2018]_ (Noisy Intermediate-Scale Quantum) era is characterised by having low numbers of qubits and high error rates. Running meaningful examples of the classic quantum algorithms would require circuits far larger than could be executed before the quantum state is dominated by the noise. Whilst quantum error correction is intended to reduce the effect of noise channels, we are not yet at the point of being able to exploit this since we lack the number of qubits for good code distances and the error rates are far beyond the code thresholds. With noise this high, every gate counts, so being able to simplify and reduce each circuit as much as possible is crucial to getting the best results.

The devices will often only support a small (but universal) fragment of quantum circuits, either constrained by the engineering difficulty of building the necessary control systems or imposed artificially because the extreme noise in some operations would render the state unusable. Good examples of these are the heterogeneous architectures of most hardware where it may only be possible to perform multi-qubit operations between specific pairs of qubits, and the delayed-measurement model where all measurements must occur in a single layer at the end of the circuit (the measurement operations are effectively destructive and the remaining quantum state would not survive the measurement and reinitialisation of a qubit). In theory, it is still possible to perform arbitrary quantum computation with these restrictions, but there are additional resource costs that are introduced by adapting an experiment to fit and they can outright eliminate the possibility of some techniques, like error correction, that rely on mid-circuit measurement and fast feedback.

.. Differences between textbook and practical QC

Practical quantum computing in the near term differs significantly from the textbook ideals, as great attention must be paid to the fine details of each circuit, eliminating redundancy and mitigating noise wherever possible to obtain the most accurate results. Some constructions, like synthesising an arbitrary unitary or even just adding a control qubit onto a unitary, which are fine in the asymptotic limit are no longer viable in general as the scaling constant is still too high to generate efficient circuits in the device's primitives.

Even the classical processing around the quantum computation would require adjustment to account for noise, such as working with distributions over outcomes even when the algorithm expects a single definite measurement outcome, or using optimisation and learning methods that are robust to noise.

Many of the intricacies of NISQ devices can be handled automatically by tools like ``pytket``, lowering the barrier to getting competitive results from quantum hardware and freeing the user to focus on the technique or project they are working on.

Quantum Compilation
-------------------

.. Classify both circuit compilation and more generally for experiments, employing error mitigation and transformation techniques in advance of runtime

There are numerous definitions of quantum compilation used in the literature, from constructing a unitary from a problem description, to decomposing a unitary matrix into elementary gates, or the generation of a pulse schedule from a sequence of gates. These all fall under the broad idea that we are converting from a generic description of the computation we wish to perform to a description that is actually possible to run on a quantum device. The compiler in tket focuses on circuit compilation: taking a circuit representation of the procedure (possibly with small high-level components like embedded unitaries or evolution operators) and solving the gate-level constraints of the target device such as the restricted gateset, heterogeneous couplings, and measurement model.

.. Benefits of good compilation

Compilation of circuits does not have a unique solution, and whilst each solution would perform the same procedure on a perfect simulation they will have distinct noise characteristics, largely driven by the quantity and scheduling of the more expensive gates on devices. For example, the fidelities of two-qubit gates are typically an order of magnitude worse than for single-qubit gates on most current hardware [Arut2019]_, so solutions that require fewer swap gates to conform to the connectivity are likely to yield more reliable results. Making good use of the state-of-the-art in compilation techniques and codesign of the compilation strategy with the circuit structure can give significant reductions in the circuit size, which not only speeds up the computation but also increases the quality of the output and allows for larger problem instances to be considered.

Platform-Agnosticism
--------------------

Platform agnosticism is the principle that the tools and software built can be made independent of the target hardware that it will run on, and conversely that the utilisation of desirable devices is not locked behind specific interface software.

.. Freedom of choice for input language

Providing the freedom of choice for input language allows active developers and researchers to reuse existing code solutions or use software that presents the right level of abstraction and useful high-level constructions relevant to their domain without sacrificing the ability to target backends from other providers.

.. Hardware independence
.. Reusability of code and hot-swapping
.. Futureproof tools

The ability to abstract away the nuances of the hardware and work independently of the device improves the reusability of code, allowing experiments to be quickly rerun on different backends with minimal code changes (often simply hot-swapping the single line of code for connecting to the backend). In turn, this makes the high-level tools you develop to be more futureproof, as they can react to the availability of newer and better quantum hardware or changes to the capabilities and characteristics of a particular device over the course of its lifetime.

.. Modular extensions

Tket enables this by providing an intermediate language for conversion of circuits between a large number of other quantum software frameworks. The uniform interface given to supported backends allows them to be seamlessly inserted into high-level code and the transfer of control from the user's input platform of choice to the system that handles the device connection is performed automatically upon submitting circuits to be executed. The modular packaging of tket into the core ``pytket`` package and a collection of extensions allows this greater software flexibility with minimal redundant package dependencies. An extension module is provided for each compatible framework or device provider, which adds in the methods for converting primitives to and from the representation used in ``pytket`` and wrappers for presenting the backends through the standard interface.

Installation
------------

.. license
.. pip install pytket

Tket is currently available through its pythonic realisation ``pytket``, which is freely available under the Apache 2 license. To install using the ``pip`` package manager, just run ``pip install pytket`` from your terminal. Each extension module can also be installed similarly as ``pip install pytket_X``, e.g. ``pip install pytket_qiskit``.

.. Link to troubleshooting

``pytket`` is available for python versions 3.8-10 on Linux, MacOS, and Windows. For any difficulties with installation, please consult our `troubleshooting <https://tket.quantinuum.com/api-docs/install.html>`_ page.

How To Cite
-----------

.. Instructions and link to paper

If you wish to cite tket in any academic publications, we generally recommend citing our `software overview paper <https://iopscience.iop.org/article/10.1088/2058-9565/ab8e92>`_ for most cases.

If your work is on the topic of specific compilation tasks, it may be more appropriate to cite one of our other papers:

- `"On the qubit routing problem" <https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.TQC.2019.5>`_ for qubit placement (aka allocation, mapping) and routing (aka swap network insertion, connectivity solving).
- `"Phase Gadget Synthesis for Shallow Circuits" <https://arxiv.org/abs/1906.01734v2>`_ for representing exponentiated Pauli operators in the ZX calculus and their circuit decompositions.
- `"A Generic Compilation Strategy for the Unitary Coupled Cluster Ansatz" <https://arxiv.org/abs/2007.10515>`_ for sequencing of terms in Trotterisation and Pauli diagonalisation.

We are also keen for others to benchmark their compilation techniques against us. We recommend checking our `benchmark repository <https://github.com/CQCL/tket_benchmarking>`_ for examples on how to run basic benchmarks with the latest version of ``pytket``. Please list the release version of ``pytket`` with any benchmarks you give, and feel free to get in touch for any assistance needed in setting up fair and representative tests.

Support
-------

.. Github issues

If you spot any bugs or have any feature suggestions, feel free to add to the issues board on our `Github repository <https://github.com/CQCL/tket>`_. We appreciate exact error messages and reproduction steps where possible for bug reports to help us address them quickly.

.. For more specific assistance, e-mail tket-support
.. To open up direct support channels or collaboration with teams, e-mail Denise?

There is a public slack channel for community discussion and support. Click `here <https://join.slack.com/t/tketusers/shared_invite/zt-18qmsamj9-UqQFVdkRzxnXCcKtcarLRA>`_ to join.

You can also join our `mailing list <https://list.cambridgequantum.com/cgi-bin/mailman/listinfo/tket-users>`_ for updates on new ``pytket`` releases and features. If you would like to open up direct support channels for your team, engage in research collaborations, or inquire about commercial licenses, please get in touch with us (info@cambridgequantum.com). If you have support questions please send them to tket-support@cambridgequantum.com. 


.. [Pres2018] Preskill, J., 2018. Quantum Computing in the NISQ era and beyond. Quantum, 2, p.79.
.. [Arut2019] Arute, F., Arya, K., Babbush, R., Bacon, D., Bardin, J.C., Barends, R., Biswas, R., Boixo, S., Brandao, F.G., Buell, D.A. and Burkett, B., 2019. Quantum supremacy using a programmable superconducting processor. Nature, 574(7779), pp.505-510.
