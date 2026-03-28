# Default dashboard config — used as seed data for fresh deployments.
# This mirrors the hardcoded courses[] array from Dashboard.tsx.

DEFAULT_DASHBOARD_CONFIG = {
    "sections": [
        {"id": "foundations", "title": "Foundations", "order": 0, "courses": [0, 1, 2]},
        {"id": "in-action", "title": "Quantum computing in action", "order": 1, "courses": [3, 4, 5]},
        {"id": "deep-dive", "title": "Deep dive into quantum theory", "order": 2, "courses": [6, 7, 8]},
    ],
    "courses": [
        {
            "id": 0,
            "title": "Introduction to Quantum Computing",
            "description": "Discover what quantum computing is and how it differs from classical computing.",
            "image": "lesson-0",
            "concepts": [
                {
                    "id": "basics",
                    "title": "Quantum Computing Fundamentals",
                    "topics": [
                        {
                            "id": 0,
                            "title": "Welcome to Quantum Computing",
                            "description": "Discover what quantum computing is and how it differs from classical computing.",
                            "implemented": True,
                        },
                        {
                            "id": 50,
                            "title": "Classical Computing Review",
                            "description": "Review the fundamentals of classical computing before diving into quantum.",
                            "implemented": False,
                        },
                        {
                            "id": 51,
                            "title": "Quantum Advantage",
                            "description": "Learn about quantum supremacy and where quantum computers excel.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 1,
            "title": "Basic Quantum Principles",
            "description": "Understand wave-particle duality, superposition, entanglement, and more.",
            "image": "lesson-1",
            "concepts": [
                {
                    "id": "core-concepts",
                    "title": "Qubits, Superposition, and Entanglement",
                    "topics": [
                        {
                            "id": 1,
                            "title": "Basic Quantum Principles",
                            "description": "Understand wave-particle duality, superposition, entanglement, and more.",
                            "implemented": True,
                        },
                        {
                            "id": 52,
                            "title": "Qubits: A Quick Recap",
                            "description": "Deep dive into the fundamental unit of quantum information.",
                            "implemented": False,
                        },
                        {
                            "id": 53,
                            "title": "Superposition in Detail",
                            "description": "Explore how quantum states can exist in multiple configurations.",
                            "implemented": False,
                        },
                    ],
                },
                {
                    "id": "measurements",
                    "title": "Quantum Measurements",
                    "topics": [
                        {
                            "id": 54,
                            "title": "Measurement Basics",
                            "description": "Learn how quantum measurements collapse superposition states.",
                            "implemented": False,
                        },
                        {
                            "id": 55,
                            "title": "Measurement Effects",
                            "description": "Understand the probabilistic nature of quantum measurements.",
                            "implemented": False,
                        },
                        {
                            "id": 56,
                            "title": "Practical Measurements",
                            "description": "Explore real-world quantum measurement techniques.",
                            "implemented": False,
                        },
                    ],
                },
                {
                    "id": "applications",
                    "title": "Real-world Applications",
                    "topics": [
                        {
                            "id": 57,
                            "title": "Quantum Sensing",
                            "description": "Discover how quantum mechanics enables ultra-precise measurements.",
                            "implemented": False,
                        },
                        {
                            "id": 58,
                            "title": "Quantum Communication",
                            "description": "Learn about quantum teleportation and secure communication.",
                            "implemented": False,
                        },
                        {
                            "id": 59,
                            "title": "Early Quantum Computers",
                            "description": "Explore the first generation of quantum computing devices.",
                            "implemented": False,
                        },
                    ],
                },
            ],
        },
        {
            "id": 2,
            "title": "Quantum Gates and Circuits (Basics)",
            "description": "Explore how quantum gates form the building blocks of quantum circuits.",
            "image": "lesson-2",
            "concepts": [
                {
                    "id": "single-gates",
                    "title": "Single Qubit Gates",
                    "topics": [
                        {
                            "id": 2,
                            "title": "Quantum Gates and Circuits (Basics)",
                            "description": "Explore how quantum gates form the building blocks of quantum circuits.",
                            "implemented": True,
                        },
                        {
                            "id": 60,
                            "title": "Pauli Gates",
                            "description": "Learn about the fundamental X, Y, and Z quantum gates.",
                            "implemented": False,
                        },
                        {
                            "id": 61,
                            "title": "Hadamard Gate",
                            "description": "Understand the gate that creates quantum superposition.",
                            "implemented": False,
                        },
                    ],
                },
                {
                    "id": "multi-gates",
                    "title": "Multi-Qubit Gates",
                    "topics": [
                        {
                            "id": 62,
                            "title": "CNOT Gate",
                            "description": "Master the controlled-NOT gate for quantum entanglement.",
                            "implemented": False,
                        },
                        {
                            "id": 63,
                            "title": "Toffoli Gate",
                            "description": "Explore reversible quantum computing with the Toffoli gate.",
                            "implemented": False,
                        },
                        {
                            "id": 64,
                            "title": "Controlled Operations",
                            "description": "Learn how to build complex controlled quantum operations.",
                            "implemented": False,
                        },
                    ],
                },
                {
                    "id": "circuits",
                    "title": "Building Circuits",
                    "topics": [
                        {
                            "id": 65,
                            "title": "Circuit Basics",
                            "description": "Understand how to construct and read quantum circuits.",
                            "implemented": False,
                        },
                        {
                            "id": 66,
                            "title": "Circuit Analysis",
                            "description": "Learn to analyze and optimize quantum circuit performance.",
                            "implemented": False,
                        },
                        {
                            "id": 67,
                            "title": "Simple Algorithms",
                            "description": "Build your first quantum algorithms using basic gates.",
                            "implemented": False,
                        },
                    ],
                },
            ],
        },
        {
            "id": 3,
            "title": "Getting Hands-On",
            "description": "Learn practical quantum computing with real-world examples.",
            "image": "lesson-0",
            "concepts": [
                {
                    "id": "practical",
                    "title": "Practical Implementation",
                    "topics": [
                        {
                            "id": 3,
                            "title": "Getting Hands-on",
                            "description": "Learn practical quantum computing with real-world examples.",
                            "implemented": True,
                        },
                        {
                            "id": 68,
                            "title": "Qiskit Basics",
                            "description": "Get started with IBM's quantum computing framework.",
                            "implemented": False,
                        },
                        {
                            "id": 69,
                            "title": "Running on Real Hardware",
                            "description": "Execute quantum circuits on actual quantum computers.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 4,
            "title": "Foundations for Quantum Computing",
            "description": "Dive deeper into the essential math and physics behind quantum computing.",
            "image": "lesson-1",
            "concepts": [
                {
                    "id": "foundations",
                    "title": "Mathematical Foundations",
                    "topics": [
                        {
                            "id": 4,
                            "title": "Foundations for Quantum Computing",
                            "description": "Dive deeper into the essential math and physics behind quantum computing.",
                            "implemented": True,
                        },
                        {
                            "id": 70,
                            "title": "Linear Algebra Review",
                            "description": "Master the mathematical tools needed for quantum mechanics.",
                            "implemented": False,
                        },
                        {
                            "id": 71,
                            "title": "Complex Numbers",
                            "description": "Understand complex numbers and their role in quantum states.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 5,
            "title": "Quantum Cryptography & Security",
            "description": "Learn how quantum computing impacts cryptography, encryption and security protocols.",
            "image": "lesson-2",
            "concepts": [
                {
                    "id": "cryptography",
                    "title": "Quantum Security",
                    "topics": [
                        {
                            "id": 5,
                            "title": "Quantum Cryptography & Security",
                            "description": "Learn how quantum computing impacts cryptography, encryption and security protocols.",
                            "implemented": True,
                        },
                        {
                            "id": 72,
                            "title": "BB84 Protocol",
                            "description": "Discover the first quantum key distribution protocol.",
                            "implemented": False,
                        },
                        {
                            "id": 73,
                            "title": "Post-Quantum Cryptography",
                            "description": "Explore encryption methods that resist quantum attacks.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 6,
            "title": "Adiabatic Quantum Computing",
            "description": "Explore the adiabatic model and quantum annealing techniques.",
            "image": "lesson-0",
            "concepts": [
                {
                    "id": "adiabatic",
                    "title": "Adiabatic Computing",
                    "topics": [
                        {
                            "id": 6,
                            "title": "Adiabatic Quantum Computing",
                            "description": "Explore the adiabatic model and quantum annealing techniques.",
                            "implemented": True,
                        },
                        {
                            "id": 74,
                            "title": "D-Wave Systems",
                            "description": "Learn about commercial quantum annealing systems.",
                            "implemented": False,
                        },
                        {
                            "id": 75,
                            "title": "Optimization Problems",
                            "description": "Apply quantum annealing to solve complex optimization challenges.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 7,
            "title": "Quantum Signal Processing & Simulation",
            "description": "Understand how quantum systems simulate complex physical processes.",
            "image": "lesson-1",
            "concepts": [
                {
                    "id": "signal-processing",
                    "title": "Signal Processing & Simulation",
                    "topics": [
                        {
                            "id": 7,
                            "title": "Quantum Signal Processing & Simulation",
                            "description": "Understand how quantum systems simulate complex physical processes.",
                            "implemented": True,
                        },
                        {
                            "id": 76,
                            "title": "Phase Estimation",
                            "description": "Master the quantum phase estimation algorithm.",
                            "implemented": False,
                        },
                        {
                            "id": 77,
                            "title": "Quantum Fourier Transform",
                            "description": "Learn the quantum version of the discrete Fourier transform.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 8,
            "title": "Quantum Hardware & Future Trends",
            "description": "Discover the cutting-edge hardware behind quantum computers.",
            "image": "lesson-2",
            "concepts": [
                {
                    "id": "hardware",
                    "title": "Hardware & Future",
                    "topics": [
                        {
                            "id": 8,
                            "title": "Quantum Hardware & Future Trends",
                            "description": "Discover the cutting-edge hardware behind quantum computers.",
                            "implemented": True,
                        },
                        {
                            "id": 78,
                            "title": "Superconducting Qubits",
                            "description": "Explore superconducting quantum computing architectures.",
                            "implemented": False,
                        },
                        {
                            "id": 79,
                            "title": "Trapped Ion Systems",
                            "description": "Learn about trapped ion quantum computing platforms.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
    ],
}
