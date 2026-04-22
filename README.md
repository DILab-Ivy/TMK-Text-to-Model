# Text-to-Model (TTM) Pipeline for Procedural Skill Modeling

Supplementary materials for:

> Dass, R. K., Puri, S., Khandelwal, A., Jin, X., & Goel, A. K. (2026). Developing 
> Models of Procedural Skills using an AI-assisted Text-to-Model Approach. 
> *ACM Learning@Scale 2026*. https://arxiv.org/abs/2604.17624

This repository contains the tools and resources for transforming instructional 
materials into structured Task-Method-Knowledge (TMK) models, as detailed in the 
paper above.

---

### TMK Modelling Gem

The TTM pipeline is implemented as a configured Gemini 3 instance (a "Gem") 
pre-loaded with the system prompt and TMK reference materials.

[Access the TMK Modelling Gem here.](https://gemini.google.com/gem/1gmgzQEAYM1SwuIyN4sI85gImBYeYCEj-?usp=sharing)

### Usage Instructions

To generate a new Raw TMK draft:

1. Upload your course material (textbooks, transcripts, or PDFs) to the 
[TMK Modelling Gem](https://gemini.google.com/gem/1gmgzQEAYM1SwuIyN4sI85gImBYeYCEj-?usp=sharing).
2. Enter the following prompt:

> Read the attached PDF and draft a TMK model on [lesson name].

### Validation and Refinement

* **Validate:** The `tmk-syntax-validator` can be used to validate the generated 
`Task.json`, `Method.json`, and `Knowledge.json`. This static web app contains 
the official standards-compliant TMK schemata required to ensure structural integrity.
* **Refine:** Current workflows require manual refinement using a text or code editor. 
Proofread and refine the models, paying special attention to content coverage, causal 
transitions, state logic, and domain-specific edge cases.
  * **Note:** We are currently developing a more user-friendly application to 
  streamline this refinement process.

---

### Repository Contents

* **[TMK JSON Schemata](https://github.com/DILab-Ivy/TMK-Text-to-Model/tree/main/tmk-syntax-validator/schemata)**: Used to constrain the Gem's draft models.
* **[ExampleModels/](https://github.com/DILab-Ivy/TMK-Text-to-Model/tree/main/ExampleModels)**: 
Contains the two primary examples discussed in the paper (Frames, IUPAC Nomenclature). 
Specific commits are included so readers can use a diff to compare the Raw LLM output 
against the expert-refined version.
  * **[Frames lesson diff](https://github.com/DILab-Ivy/TMK-Text-to-Model/commit/b9f4c09a5591b316649d56487b83110b27483cd1)**: For a lesson in a graduate-level Knowledge-Based AI course at Georgia Tech.
  * **[IUPAC Nomenclature lesson diff](https://github.com/DILab-Ivy/TMK-Text-to-Model/commit/8317237e0ddd0b176beca2e228c34940357a7cb2)**: For a foundational organic chemistry skill, based on IUPAC's Blue Book.
* **[EvaluationScripts/](https://github.com/DILab-Ivy/TMK-Text-to-Model/tree/main/EvaluationScripts)**: 
Contains the scripts used to calculate the semantic similarity results reported in 
the paper.
* **[SystemPrompt/](https://github.com/DILab-Ivy/TMK-Text-to-Model/tree/main/SystemPrompt)**: 
Contains the full system prompt used to configure the TMK Modelling Gem.
* **[tmk-syntax-validator/](https://github.com/DILab-Ivy/TMK-Text-to-Model/tree/main/tmk-syntax-validator)**: 
The static web app to validate TMK models against the TMK schemata.

---

### Contact

If you have any questions about this repository or the paper, please contact:

* **Rahul Dass** — rdass7@gatech.edu
* **Shubham Puri** — spuri62@gatech.edu
