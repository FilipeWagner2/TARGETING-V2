import unittest
from pathlib import Path

import teste


class TargetingV2Tests(unittest.TestCase):
    def test_detect_user_intent(self) -> None:
        self.assertEqual(teste.detect_user_intent("Tem um erro no controller e preciso corrigir"), "debugging")
        self.assertEqual(teste.detect_user_intent("Explique a arquitetura e os modulos"), "arquitetura")
        self.assertEqual(teste.detect_user_intent("Implemente um endpoint novo"), "implementacao")

    def test_render_standard_response_has_fixed_sections(self) -> None:
        chunks = [
            {"path": "src/app.py", "start_line": 10, "end_line": 20},
            {"path": "README.md", "start_line": 1, "end_line": 8},
        ]
        structure = {
            "repo_id": "demo_repo",
            "total_indexed_files": 2,
            "top_level_directories": ["src"],
            "top_level_files": ["README.md"],
            "languages": {"Python": 1, "Markdown": 1},
            "framework_signals": ["python-project"],
            "entrypoints": ["src/app.py"],
        }

        formatted = teste.render_standard_response(
            raw_answer="Resumo principal.\n\nDetalhes adicionais.",
            retrieved_chunks=chunks,
        )

        self.assertIn("Resumo principal.", formatted)
        self.assertIn("Detalhes adicionais.", formatted)
        self.assertIn("--- Evidencias (arquivos/linhas) ---", formatted)
        self.assertIn("--- Qualidade do contexto ---", formatted)
        self.assertIn("- src/app.py:10-20", formatted)

    def test_build_structure_summary_detects_dotnet(self) -> None:
        indexed_paths = {
            "Program.cs",
            "ProjetoCUP.csproj",
            "Controllers/PacientesController.cs",
            "README.md",
        }

        structure = teste.build_structure_summary("cup_repo", indexed_paths)

        self.assertEqual(structure["repo_id"], "cup_repo")
        self.assertIn("dotnet-project", structure["framework_signals"])
        self.assertIn("Program.cs", structure["entrypoints"])
        self.assertGreaterEqual(structure["total_indexed_files"], 4)

    def test_extract_question_without_url(self) -> None:
        question = teste.extract_question_without_url(
            "Acesse https://github.com/octocat/Hello-World e me explique a arquitetura",
            "https://github.com/octocat/Hello-World",
        )
        self.assertTrue("arquitetura" in question.lower())

    def test_supports_extensionless_file_for_better_coverage(self) -> None:
        self.assertTrue(teste.is_supported_file(Path("Jenkinsfile")))
        self.assertTrue(teste.is_supported_file(Path("Procfile")))
        self.assertTrue(teste.is_supported_file(Path("SCRIPT_SEM_EXTENSAO")))

    def test_structure_summary_has_layers_and_key_files(self) -> None:
        indexed_paths = {
            "Controllers/PacientesController.cs",
            "Models/Paciente.cs",
            "Data/AppDbContext.cs",
            "Program.cs",
            "README.md",
        }
        structure = teste.build_structure_summary("repo_demo", indexed_paths)
        self.assertIn("layers", structure)
        self.assertIn("key_files", structure)
        self.assertTrue(any(name.endswith("Program.cs") for name in structure["key_files"]))


if __name__ == "__main__":
    unittest.main()
