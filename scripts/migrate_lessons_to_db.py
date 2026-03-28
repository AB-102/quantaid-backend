"""
Migration script: Convert hardcoded LessonContents.ts and QuizQuestion.ts data
into the new lessons_v2 MongoDB collection with block-based content.

Usage:
    python scripts/migrate_lessons_to_db.py

This script is idempotent — it skips courseIds that already exist in lessons_v2.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import UTC, datetime

from database.mongo import db

# --- Hardcoded lesson data (mirrored from LessonContents.ts) ---

LESSONS = {
    0: {
        "title": "Welcome to Quantum Computing",
        "paragraphs": [
            "Quantum computing is a revolutionary technology that harnesses the principles of quantum mechanics to perform computations far beyond the capability of classical computers. These principles enable new ways of processing information that are fundamentally different from binary logic.",
            "Highlight any text to get options, or click underlined terms like qubit, superposition, and entanglement to learn more!",
            {"text": "Core Principles", "type": "heading"},
            "Qubits: Unlike classical bits, which are strictly 0 or 1, qubits can exist in a combination of both states simultaneously. This property, called superposition, provides quantum computers with unparalleled computational power for specific tasks.",
            "Superposition: Superposition enables a single qubit to represent multiple possibilities at once. For example, while a classical bit can only encode one number (0 or 1), a qubit in superposition can encode a combination of both. This property allows quantum computers to process many potential solutions simultaneously, exponentially increasing computational efficiency for some problems.",
            "Entanglement: Entanglement links two or more qubits such that the state of one immediately affects the state of the other, regardless of distance. This phenomenon forms the backbone of quantum communication and allows quantum computers to perform coordinated calculations across multiple qubits.",
            "Measurement: Measurement is the process of observing a qubit, which collapses its superposition into a definite state. This final state provides the result of a quantum computation, though the probabilistic nature of quantum mechanics means results may vary.",
            {"text": "Applications", "type": "heading"},
            "Cryptography: Quantum computers can break classical encryption methods, such as RSA, by efficiently factoring large numbers using algorithms like Shor's Algorithm. At the same time, they enable the creation of quantum-safe encryption methods, ensuring secure communication in the quantum era.",
            "Drug Discovery and Materials Science: By simulating molecular interactions at the quantum level, quantum computers can accelerate the discovery of new drugs and materials\u2014critical for breakthroughs in medicine and materials science.",
            "Optimization: Many industries face optimization challenges\u2014from supply chain logistics to portfolio management in finance. Quantum computers can evaluate multiple solutions simultaneously, offering potential speedups for finding optimal solutions.",
        ],
        "interactiveTerms": {
            "qubit": "A quantum bit (qubit) is the basic unit of quantum information. Unlike a classical bit, which must be 0 or 1, a qubit can be 0, 1, or any superposition of these states until measured.",
            "superposition": "Superposition is a fundamental principle of quantum mechanics where a quantum system (like a qubit) can exist in multiple states at the same time. Only when measured does it collapse to a single definite outcome.",
            "entanglement": "Entanglement is a quantum phenomenon where two or more qubits become linked such that measuring one instantly influences the state of the other, no matter the distance separating them.",
            "measurement": "Measurement in quantum mechanics is the act of observing a quantum system. This observation forces the system to choose a definite classical state, collapsing any superposition.",
        },
    },
    1: {
        "title": "Basic Quantum Principles",
        "paragraphs": [
            "In this lesson, we cover the foundational ideas that make quantum computing possible.",
            {"text": "Key Concepts", "type": "heading"},
            {"text": "Wave-Particle Duality", "type": "subheading"},
            "Quantum objects can behave both as particles and as waves, depending on how they are observed.",
            {"text": "Superposition", "type": "subheading"},
            "A qubit in superposition can exist in many possible states at once, enabling parallelism in computation.",
            {"text": "Entanglement", "type": "subheading"},
            "When qubits become entangled, their states are correlated in such a way that the measurement of one determines the state of the other instantly.",
            {"text": "Measurement Collapse", "type": "subheading"},
            "Observing a qubit forces it into one of its basis states, destroying its previous superposition.",
            {"text": "Applications", "type": "heading"},
            "These principles underpin advanced algorithms like Grover's search and quantum teleportation, which exploit superposition and entanglement for speedups.",
        ],
        "interactiveTerms": {
            "wave-particle duality": "Wave-particle duality is the concept that every quantum entity exhibits both wave-like and particle-like properties.",
            "superposition": "Superposition allows a qubit to be in a combination of the |0\u27e9 and |1\u27e9 states until measurement.",
            "entanglement": "Entanglement links qubit states so that they cannot be described independently of each other.",
            "measurement collapse": "Measurement collapse is when observing a quantum system forces it into one definite state, ending superposition.",
        },
    },
    2: {
        "title": "Quantum Gates and Circuits (Basics)",
        "paragraphs": [
            "Quantum gates are the building blocks of quantum algorithms, analogous to classical logic gates.",
            {"text": "Basic Gates", "type": "heading"},
            {"text": "Hadamard Gate (H)", "type": "subheading"},
            "Puts a single qubit into an equal superposition of |0\u27e9 and |1\u27e9.",
            {"text": "Pauli-X Gate", "type": "subheading"},
            "Flips the state of a qubit, analogous to a classical NOT gate.",
            {"text": "CNOT Gate", "type": "subheading"},
            "A two-qubit gate that flips the second qubit (target) if the first qubit (control) is |1\u27e9.",
            {"text": "Building Circuits", "type": "heading"},
            {"text": "Circuit Diagrams", "type": "subheading"},
            "Represent qubits as horizontal lines and gates as symbols placed on those lines in sequence.",
            "By combining gates, you can build complex quantum circuits to implement powerful algorithms.",
        ],
        "interactiveTerms": {
            "Hadamard Gate": "The Hadamard gate creates equal superposition, mapping |0\u27e9 \u2192 (|0\u27e9+|1\u27e9)/\u221a2 and |1\u27e9 \u2192 (|0\u27e9\u2212|1\u27e9)/\u221a2.",
            "Pauli-X Gate": "The Pauli-X gate acts like a NOT gate, flipping |0\u27e9 \u2194 |1\u27e9 on a qubit.",
            "CNOT": "The CNOT (Controlled NOT) gate flips the target qubit if the control qubit is in state |1\u27e9.",
            "Circuit Diagrams": "Quantum circuit diagrams visually depict the sequence of gates applied to qubits over time.",
        },
    },
    3: {
        "title": "Getting Hands-on",
        "paragraphs": [
            "Now let's write some actual quantum code using Qiskit.",
            {"text": "Qiskit Framework", "type": "heading"},
            "Qiskit is an open-source Python framework for creating and running quantum circuits on simulators or real hardware.",
            {"text": "Core Components", "type": "subheading"},
            "QuantumCircuit Object: Build circuits by instantiating a QuantumCircuit and adding gates.",
            "Transpilation: Converts your high-level description into low-level instructions optimized for a given backend.",
            {"text": "Execution", "type": "subheading"},
            "Submit jobs to IBM Quantum simulators or real devices via the IBM Quantum Experience.",
            "Experiment with small circuits, view results, and analyze outcomes to deepen your understanding.",
        ],
        "interactiveTerms": {
            "Qiskit": "Qiskit is IBM's open-source SDK for working with quantum computers at the level of circuits, pulses, and algorithms.",
            "QuantumCircuit": "A QuantumCircuit object in Qiskit holds qubits, classical bits, and the sequence of gates to be executed.",
            "IBM Quantum Experience": "IBM Quantum Experience is a cloud platform where you can run quantum jobs on simulators and actual quantum processors.",
        },
    },
    4: {
        "title": "Foundations for Quantum Computing",
        "paragraphs": [
            "This lesson dives into the math underpinning quantum theory.",
            {"text": "Mathematical Foundations", "type": "heading"},
            {"text": "Dirac Notation", "type": "subheading"},
            "Uses |\u03c8\u27e9 to denote quantum states and \u27e8\u03c6| for bra vectors.",
            {"text": "Hilbert Space", "type": "subheading"},
            "The vector space in which quantum states live, equipped with an inner product.",
            {"text": "Bloch Sphere", "type": "subheading"},
            "A geometric representation of the state of a single qubit on the surface of a sphere.",
            {"text": "Complex Amplitudes", "type": "subheading"},
            "Probability amplitudes are complex numbers whose magnitudes squared give measurement probabilities.",
            {"text": "Practical Applications", "type": "heading"},
            "Understanding these foundations will help you follow advanced algorithms and error-correction schemes.",
        ],
        "interactiveTerms": {
            "Dirac Notation": "Dirac (bra-ket) notation succinctly represents quantum states: |\u03c8\u27e9 is a ket vector, \u27e8\u03c8| is its dual bra.",
            "Bloch Sphere": "The Bloch sphere visually represents the state of a qubit as a point on or inside a unit sphere.",
        },
    },
    5: {
        "title": "Quantum Cryptography & Security",
        "paragraphs": [
            "Quantum mechanics not only breaks classical cryptography but also enables new secure protocols.",
            {"text": "Quantum Key Distribution", "type": "heading"},
            {"text": "BB84 Protocol", "type": "subheading"},
            "Uses polarized photons to share encryption keys with guaranteed eavesdrop detection.",
            {"text": "QKD Implementation", "type": "subheading"},
            "Allows two parties to generate a shared, secret key with security based on physics.",
            {"text": "Classical Resistance", "type": "heading"},
            {"text": "Post-Quantum Cryptography", "type": "subheading"},
            "Classical algorithms designed to resist attacks by quantum computers.",
            {"text": "Current Applications", "type": "subheading"},
            "Fiber-optic and free-space QKD systems are already in use for secure communication.",
        ],
        "interactiveTerms": {
            "BB84": "BB84 is the first QKD protocol, using four polarization states of photons to establish secure keys.",
            "Quantum Key Distribution": "QKD enables two parties to share a secret key with security guaranteed by the laws of quantum mechanics.",
        },
    },
    6: {
        "title": "Adiabatic Quantum Computing",
        "paragraphs": [
            "Adiabatic quantum computing encodes solutions to optimization problems in the ground state of a Hamiltonian.",
            {"text": "Theoretical Foundation", "type": "heading"},
            {"text": "Adiabatic Theorem", "type": "subheading"},
            "A quantum system remains in its instantaneous ground state if changes are sufficiently slow.",
            {"text": "Quantum Annealing", "type": "subheading"},
            "Slowly evolves the Hamiltonian from an easy initial form to one encoding the problem.",
            {"text": "Commercial Implementation", "type": "heading"},
            {"text": "D-Wave Systems", "type": "subheading"},
            "Commercial quantum annealers built by D-Wave implement quantum annealing on hundreds of qubits.",
            {"text": "Applications", "type": "subheading"},
            "Particularly suited for combinatorial optimization, scheduling, and materials modeling.",
        ],
        "interactiveTerms": {
            "Adiabatic Theorem": "The adiabatic theorem states that a quantum system stays in its ground state when its Hamiltonian changes slowly enough.",
            "Quantum Annealing": "Quantum annealing leverages the adiabatic theorem to solve optimization problems by evolving toward a problem Hamiltonian.",
        },
    },
    7: {
        "title": "Quantum Signal Processing & Simulation",
        "paragraphs": [
            "Quantum signal processing uses controlled quantum evolutions to perform spectral transformations.",
            {"text": "Core Algorithms", "type": "heading"},
            {"text": "Phase Estimation", "type": "subheading"},
            "Determines eigenvalues of a unitary operator, a key subroutine in many algorithms.",
            {"text": "Hamiltonian Simulation", "type": "subheading"},
            "Mimics the evolution of a quantum system under a given Hamiltonian.",
            {"text": "Transform Methods", "type": "heading"},
            {"text": "Quantum Fourier Transform (QFT)", "type": "subheading"},
            "The quantum analogue of the discrete Fourier transform with exponential speedup.",
            {"text": "Applications", "type": "subheading"},
            "Used in algorithms for chemistry, cryptanalysis, and solving linear systems of equations.",
        ],
        "interactiveTerms": {
            "Phase Estimation": "Phase estimation finds the phase (eigenvalue) of an eigenstate of a unitary operator using interference.",
            "Hamiltonian Simulation": "Hamiltonian simulation reproduces the dynamics of a quantum system, enabling study of complex molecules on a quantum computer.",
        },
    },
    8: {
        "title": "Quantum Hardware & Future Trends",
        "paragraphs": [
            "Quantum hardware is rapidly evolving, with multiple qubit modalities under development.",
            {"text": "Current Technologies", "type": "heading"},
            {"text": "Superconducting Qubits", "type": "subheading"},
            "Use Josephson junctions at millikelvin temperatures to encode quantum states.",
            {"text": "Trapped Ions", "type": "subheading"},
            "Individual ions confined by electromagnetic fields offer long coherence times.",
            {"text": "Emerging Technologies", "type": "heading"},
            {"text": "Topological Qubits", "type": "subheading"},
            "Aim to encode information in nonlocal properties of quasiparticles for built-in error resistance.",
            {"text": "Future Outlook", "type": "heading"},
            "Scaling up, error correction, and hybrid quantum-classical architectures will define the next decade.",
        ],
        "interactiveTerms": {
            "Superconducting Qubits": "Superconducting qubits exploit superconductivity and Josephson junctions to create robust two-level systems.",
            "Topological Qubits": "Topological qubits store information in global properties of a system, making them inherently resistant to local noise.",
        },
    },
}


# --- Quiz data (mirrored from QuizQuestion.ts) ---

QUIZZES = {
    0: [
        {
            "question": "What is a primary difference between a qubit and a classical bit?",
            "options": [
                "A qubit can only be 0 or 1.",
                "A classical bit can be 0, 1, or both simultaneously.",
                "A qubit can be 0, 1, or a superposition of both.",
                "Classical bits are faster than qubits.",
            ],
            "correctAnswer": 2,
            "explanation": "Classical bits are limited to definite states (0 or 1), while qubits leverage superposition until measured.",
            "lessonContentIndices": [3, 4],
        },
        {
            "question": "Quantum computing promises potential advantages over classical computing primarily in which tasks?",
            "options": [
                "Word processing and spreadsheet calculations.",
                "Video streaming and web browsing.",
                "Simulating quantum systems, optimization, and cryptography.",
                "Storing large amounts of data.",
            ],
            "correctAnswer": 2,
            "explanation": "Quantum computers excel at problems intractable for classical machines, like molecular simulations or cryptanalysis.",
            "lessonContentIndices": [8, 9, 10, 11],
        },
        {
            "question": "Which phenomenon allows two qubits to exhibit correlated results instantaneously?",
            "options": ["Superposition", "Interference", "Entanglement", "Decoherence"],
            "correctAnswer": 2,
            "explanation": "Entanglement links qubit states so measuring one immediately affects the other, regardless of distance.",
            "lessonContentIndices": [5],
        },
        {
            "question": "What happens when you measure a qubit in superposition?",
            "options": [
                "It remains in superposition.",
                "It collapses to one of the basis states.",
                "It duplicates itself.",
                "It entangles with its environment.",
            ],
            "correctAnswer": 1,
            "explanation": "Measurement collapses the qubit's superposition into a definite classical state, yielding one outcome.",
            "lessonContentIndices": [6],
        },
    ],
    1: [
        {
            "question": "1) What does the principle of superposition describe?",
            "options": [
                "A quantum particle can only be in one location at a time.",
                "A qubit can exist in a combination of basis states simultaneously.",
                "Two particles linked regardless of distance.",
                "Measuring a system collapses its state.",
            ],
            "correctAnswer": 1,
            "explanation": "Superposition allows a quantum system to be in multiple states until an observation is made.",
            "lessonContentIndices": [4, 5],
        },
        {
            "question": "2) Entanglement refers to:",
            "options": [
                "Wave-like particle behavior.",
                "Particle-like wave behavior.",
                "Correlation between particles across distances.",
                "The process of measurement.",
            ],
            "correctAnswer": 2,
            "explanation": "Entangled particles have linked states such that measuring one instantly affects the other.",
            "lessonContentIndices": [6, 7],
        },
        {
            "question": "3) Which principle states measurement affects a quantum system's state?",
            "options": ["Superposition", "Entanglement", "Measurement collapse", "Wave-particle duality"],
            "correctAnswer": 2,
            "explanation": "Measurement collapse describes how observing a quantum system forces it into a definite state.",
            "lessonContentIndices": [8, 9],
        },
        {
            "question": "4) Wave-particle duality means quantum objects can behave as:",
            "options": ["Only waves.", "Only particles.", "Both waves and particles.", "Neither waves nor particles."],
            "correctAnswer": 2,
            "explanation": "Quantum entities exhibit both wave-like and particle-like properties depending on how they are measured.",
            "lessonContentIndices": [2, 3],
        },
    ],
    2: [
        {
            "question": "1) What is the quantum equivalent of a classical logic gate?",
            "options": ["A qubit", "A quantum algorithm", "A quantum gate", "A quantum measurement"],
            "correctAnswer": 2,
            "explanation": "Quantum gates operate on qubits, analogous to how classical gates operate on bits.",
            "lessonContentIndices": [0],
        },
        {
            "question": "2) The Hadamard gate is used to:",
            "options": [
                "Measure a qubit's state.",
                "Entangle two qubits.",
                "Create an equal superposition.",
                "Flip a qubit's state.",
            ],
            "correctAnswer": 2,
            "explanation": "Hadamard puts |0\u27e9 or |1\u27e9 into (|0\u27e9+|1\u27e9)/\u221a2 superposition.",
            "lessonContentIndices": [2, 3],
        },
        {
            "question": "3) What does a Pauli-X gate do?",
            "options": [
                "Creates superposition.",
                "Flips the qubit state (|0\u27e9\u2194|1\u27e9).",
                "Measures phase.",
                "Entangles qubits.",
            ],
            "correctAnswer": 1,
            "explanation": "Pauli-X is the quantum NOT gate, toggling |0\u27e9 to |1\u27e9 and vice versa.",
            "lessonContentIndices": [4, 5],
        },
        {
            "question": "4) A CNOT gate performs which action?",
            "options": [
                "Flips control qubit unconditionally.",
                "Flips target qubit if control is |1\u27e9.",
                "Measures both qubits.",
                "Creates three-qubit GHZ states.",
            ],
            "correctAnswer": 1,
            "explanation": "CNOT flips the target qubit only when the control qubit is in the |1\u27e9 state.",
            "lessonContentIndices": [6, 7],
        },
    ],
    3: [
        {
            "question": "1) In Qiskit, circuits are built using which object?",
            "options": ["Qubit", "Gate", "QuantumCircuit", "Simulator"],
            "correctAnswer": 2,
            "explanation": "QuantumCircuit is the core Qiskit class for constructing quantum circuits.",
            "lessonContentIndices": [4],
        },
        {
            "question": "2) IBM Quantum Experience allows you to:",
            "options": [
                "Build classical circuits.",
                "Run quantum jobs on real hardware.",
                "Design semiconductor chips.",
                "Perform molecular modeling.",
            ],
            "correctAnswer": 1,
            "explanation": "IBM Quantum Experience gives access to simulators and real quantum devices.",
            "lessonContentIndices": [7],
        },
        {
            "question": "3) Transpilation in Qiskit is used to:",
            "options": [
                "Visualize circuits.",
                "Optimize circuits for a backend.",
                "Measure qubits.",
                "Create entanglement.",
            ],
            "correctAnswer": 1,
            "explanation": "Transpilation rewrites circuits to match the topology and gate set of a specific hardware backend.",
            "lessonContentIndices": [5],
        },
        {
            "question": "4) A Qiskit simulator is useful for:",
            "options": [
                "Testing circuits without real-hardware noise.",
                "Launching space rockets.",
                "Detecting qubit errors on hardware.",
                "Building classical neural networks.",
            ],
            "correctAnswer": 0,
            "explanation": "Simulators let you verify and debug quantum circuits in a noise-free environment.",
            "lessonContentIndices": [8],
        },
    ],
    4: [
        {
            "question": "1) Dirac notation uses what to denote states?",
            "options": ["[ ]", "|\u27e9", "<>", "()"],
            "correctAnswer": 1,
            "explanation": "Kets like |\u03c8\u27e9 denote quantum states in Dirac notation.",
            "lessonContentIndices": [2, 3],
        },
        {
            "question": "2) The Bloch sphere represents:",
            "options": [
                "Classical bit values.",
                "A qubit's state on a sphere.",
                "Energy levels of atoms.",
                "Photon polarization.",
            ],
            "correctAnswer": 1,
            "explanation": "The Bloch sphere is a geometric representation of an arbitrary qubit state.",
            "lessonContentIndices": [6, 7],
        },
        {
            "question": "3) Hilbert space is:",
            "options": [
                "A classical memory.",
                "A vector space for quantum states.",
                "A type of quantum gate.",
                "A measurement device.",
            ],
            "correctAnswer": 1,
            "explanation": "Quantum states are vectors in a complex inner-product space called Hilbert space.",
            "lessonContentIndices": [4, 5],
        },
        {
            "question": "4) Complex amplitudes' magnitudes squared give:",
            "options": ["Phase information.", "Measurement probabilities.", "Energy values.", "Temperature data."],
            "correctAnswer": 1,
            "explanation": "The squared modulus of a quantum amplitude is the probability of that outcome.",
            "lessonContentIndices": [8, 9],
        },
    ],
    5: [
        {
            "question": "1) BB84 is a protocol for:",
            "options": [
                "Breaking RSA encryption.",
                "Quantum key distribution.",
                "Quantum teleportation.",
                "Quantum machine learning.",
            ],
            "correctAnswer": 1,
            "explanation": "BB84 is the first quantum key distribution protocol, ensuring secure key exchange.",
            "lessonContentIndices": [2, 3],
        },
        {
            "question": "2) Post-quantum cryptography refers to:",
            "options": [
                "Classical methods secure against quantum attacks.",
                "Encrypting quantum states.",
                "Teleporting encryption keys.",
                "None of the above.",
            ],
            "correctAnswer": 0,
            "explanation": "Post-quantum cryptography uses algorithms designed to resist quantum computer attacks.",
            "lessonContentIndices": [6, 7],
        },
        {
            "question": "3) In QKD, eavesdropping is detected via:",
            "options": ["Signal amplification.", "State disturbance.", "Noise suppression.", "Thermal fluctuations."],
            "correctAnswer": 1,
            "explanation": "Any measurement by an eavesdropper disturbs the quantum states, revealing their presence.",
            "lessonContentIndices": [4, 5],
        },
        {
            "question": "4) Practical QKD systems often use:",
            "options": ["Microwave signals.", "Polarized photons.", "Magnetic resonance.", "Neural networks."],
            "correctAnswer": 1,
            "explanation": "Polarized single photons carry quantum bits for secure key exchange in BB84 and similar protocols.",
            "lessonContentIndices": [8, 9],
        },
    ],
    6: [
        {
            "question": "1) Adiabatic theorem ensures:",
            "options": [
                "Instantaneous state changes.",
                "Evolution stays in ground state if slow.",
                "Random jumps between states.",
                "Measurement collapse.",
            ],
            "correctAnswer": 1,
            "explanation": "If a Hamiltonian changes slowly, the system remains in its instantaneous ground state.",
            "lessonContentIndices": [2, 3],
        },
        {
            "question": "2) Quantum annealing solves problems by:",
            "options": [
                "Rapid gate operations.",
                "Adiabatic evolution toward problem ground state.",
                "Classical optimization.",
                "Photon entanglement.",
            ],
            "correctAnswer": 1,
            "explanation": "Quantum annealing evolves the system from an easy initial Hamiltonian to one encoding the optimization problem.",
            "lessonContentIndices": [4, 5],
        },
        {
            "question": "3) D-Wave systems use which model?",
            "options": [
                "Gate-based quantum computing.",
                "Quantum annealing.",
                "Topological qubits.",
                "Optical lattices.",
            ],
            "correctAnswer": 1,
            "explanation": "D-Wave builds quantum annealers specifically designed for optimization via adiabatic quantum computing.",
            "lessonContentIndices": [7, 8],
        },
        {
            "question": "4) A key advantage of quantum annealing is:",
            "options": [
                "Error-free gates.",
                "Large-scale qubit entanglement.",
                "Direct encoding of optimization cost functions.",
                "Instant teleportation.",
            ],
            "correctAnswer": 2,
            "explanation": "Quantum annealing encodes optimization directly into a Hamiltonian, simplifying cost evaluation.",
            "lessonContentIndices": [9, 10],
        },
    ],
    7: [
        {
            "question": "1) Phase estimation determines:",
            "options": [
                "Eigenvalues of a unitary operator.",
                "Amplitude of a wave.",
                "Energy gap.",
                "Classical frequencies.",
            ],
            "correctAnswer": 0,
            "explanation": "Quantum phase estimation finds eigenvalues (phases) corresponding to eigenstates of a unitary.",
            "lessonContentIndices": [2, 3],
        },
        {
            "question": "2) Hamiltonian simulation is used to:",
            "options": [
                "Analyze classical circuits.",
                "Replicate quantum dynamics of molecules.",
                "Encrypt data.",
                "Measure qubits directly.",
            ],
            "correctAnswer": 1,
            "explanation": "Hamiltonian simulation reproduces the time evolution of quantum systems on a quantum computer.",
            "lessonContentIndices": [4, 5],
        },
        {
            "question": "3) The Quantum Fourier Transform (QFT) provides:",
            "options": [
                "Classical FFT.",
                "Exponential speedup for Fourier analysis.",
                "Error correction.",
                "Qubit measurement.",
            ],
            "correctAnswer": 1,
            "explanation": "QFT is the quantum analogue of the discrete Fourier transform, efficient on quantum hardware.",
            "lessonContentIndices": [7, 8],
        },
        {
            "question": "4) Quantum signal processing algorithms often leverage:",
            "options": ["Classical filter banks.", "Controlled-phase rotations.", "Optical tweezers.", "Neural nets."],
            "correctAnswer": 1,
            "explanation": "Controlled-phase rotations are used to implement spectral transformations in quantum signal processing.",
            "lessonContentIndices": [9, 10],
        },
    ],
    8: [
        {
            "question": "1) Superconducting qubits typically operate at:",
            "options": [
                "Room temperature.",
                "Millikelvin ranges.",
                "Liquid nitrogen temperatures.",
                "High vacuum only.",
            ],
            "correctAnswer": 1,
            "explanation": "Superconducting circuits require dilution refrigerators to reach millikelvin temperatures for coherence.",
            "lessonContentIndices": [2, 3],
        },
        {
            "question": "2) Topological qubits aim to reduce:",
            "options": ["Gate speed.", "Hardware size.", "Error rates via nonlocal encoding.", "Quantum parallelism."],
            "correctAnswer": 2,
            "explanation": "Topological qubits encode information in global states of the system, making them robust to local noise.",
            "lessonContentIndices": [6, 7],
        },
    ],
}


def paragraphs_to_blocks(paragraphs: list) -> list:
    """Convert the legacy paragraph format to block-based content."""
    blocks = []
    for item in paragraphs:
        if isinstance(item, str):
            blocks.append({"type": "paragraph", "text": item})
        elif isinstance(item, dict):
            block_type = item.get("type", "paragraph")
            blocks.append({"type": block_type, "text": item["text"]})
    return blocks


def get_lesson_documents() -> list:
    """Return all lesson documents ready for insertion (no DB side effects)."""
    now = datetime.now(UTC)
    docs = []
    for course_id in sorted(LESSONS.keys()):
        lesson_data = LESSONS[course_id]
        quiz_data = QUIZZES.get(course_id, [])
        blocks = paragraphs_to_blocks(lesson_data["paragraphs"])  # ty: ignore[invalid-argument-type]
        docs.append(
            {
                "courseId": course_id,
                "title": lesson_data["title"],
                "blocks": blocks,
                "quiz": quiz_data,
                "interactiveTerms": lesson_data.get("interactiveTerms", {}),
                "created_at": now,
                "updated_at": now,
            }
        )
    return docs


def migrate():
    now = datetime.now(UTC)
    inserted = 0
    skipped = 0

    for course_id in sorted(LESSONS.keys()):
        # Skip if already migrated
        if db.lessons_v2.find_one({"courseId": course_id}):
            print(f"  courseId={course_id} already exists, skipping")
            skipped += 1
            continue

        lesson_data = LESSONS[course_id]
        quiz_data = QUIZZES.get(course_id, [])

        blocks = paragraphs_to_blocks(lesson_data["paragraphs"])  # ty: ignore[invalid-argument-type]

        doc = {
            "courseId": course_id,
            "title": lesson_data["title"],
            "blocks": blocks,
            "quiz": quiz_data,
            "interactiveTerms": lesson_data.get("interactiveTerms", {}),
            "created_at": now,
            "updated_at": now,
        }

        db.lessons_v2.insert_one(doc)
        print(
            f'  courseId={course_id} "{lesson_data["title"]}" -> {len(blocks)} blocks, {len(quiz_data)} quiz questions'
        )
        inserted += 1

    print(f"\nDone: {inserted} lessons inserted, {skipped} skipped (already existed)")


if __name__ == "__main__":
    print("Migrating hardcoded lessons to lessons_v2 collection...")
    print(f"Database: {db.name}")
    migrate()
