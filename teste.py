import os
import json
import math
import re
import shutil
import subprocess
import textwrap
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI


RAG_ROOT = Path(__file__).resolve().parent / "rag_data"
REPOS_DIR = RAG_ROOT / "repos"
INDEX_DIR = RAG_ROOT / "indexes"

MAX_FILE_SIZE_BYTES = 300_000
MAX_CHUNK_CHARS = 1400
CHUNK_OVERLAP_LINES = 3
TOP_K = 6

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
    "__pycache__",
    ".idea",
    ".vscode",
}

SUPPORTED_EXTENSIONS = {
    ".py",
    ".md",
    ".mdx",
    ".txt",
    ".rst",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".conf",
    ".config",
    ".lock",
    ".csv",
    ".tsv",
    ".ipynb",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".mjs",
    ".cjs",
    ".java",
    ".kt",
    ".gradle",
    ".go",
    ".rs",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cs",
    ".php",
    ".rb",
    ".swift",
    ".sql",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".bat",
    ".cmd",
    ".html",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".xml",
    ".dockerfile",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".csproj",
    ".sln",
    ".props",
    ".targets",
    ".tf",
    ".hcl",
    ".proto",
}

SUPPORTED_FILENAMES = {
    "dockerfile",
    "makefile",
    "readme",
    "readme.md",
    "readme.txt",
    "license",
    "changelog",
    "requirements.txt",
    "package.json",
    "pyproject.toml",
    "poetry.lock",
    "pipfile",
    "pipfile.lock",
    "go.mod",
    "go.sum",
    "cargo.toml",
    "cargo.lock",
}

GITHUB_REPO_URL_PATTERN = re.compile(
    r"((?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?)",
    re.IGNORECASE,
)


class TermColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"


def enable_windows_ansi() -> None:
    if os.name != "nt":
        return

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def get_terminal_width() -> int:
    width = shutil.get_terminal_size(fallback=(100, 20)).columns
    return max(72, min(width, 120))


def wrap_block_text(text: str, width: int) -> list[str]:
    wrapped_lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        if not raw_line.strip():
            wrapped_lines.append("")
            continue

        wrapped = textwrap.wrap(
            raw_line,
            width=width,
            replace_whitespace=False,
            drop_whitespace=False,
        )
        wrapped_lines.extend(wrapped or [raw_line])
    return wrapped_lines


def print_panel(title: str, text: str, color: str) -> None:
    inner_width = get_terminal_width() - 4
    title_text = f" {title.upper()} "
    border = "+" + "-" * inner_width + "+"

    print(f"{color}{border}")
    print(f"|{title_text:<{inner_width}}|")
    print(border)
    for line in wrap_block_text(text, inner_width - 2):
        print(f"| {line:<{inner_width - 2}} |")
    print(f"{border}{TermColors.RESET}\n")


def print_user_message(text: str) -> None:
    print_panel("Voce", text, f"{TermColors.BOLD}{TermColors.CYAN}")


def print_agent_message(text: str) -> None:
    print_panel("Agente", text, f"{TermColors.BOLD}{TermColors.GREEN}")


def print_system_message(text: str) -> None:
    print_panel("Sistema", text, f"{TermColors.BOLD}{TermColors.YELLOW}")


def print_error_message(text: str) -> None:
    print_panel("Erro", text, f"{TermColors.BOLD}{TermColors.RED}")


def print_banner() -> None:
    print_panel(
        "RAG Chat",
        "\n".join(
            [
                "Chat iniciado.",
                "",
                "Comandos disponiveis:",
                "- ingest <url_github>  -> clona/atualiza e indexa repositorio",
                "- repos                -> lista repositorios indexados",
                "- use <repo_id>        -> seleciona repositorio ativo",
                "- coverage             -> mostra cobertura do repo ativo",
                "- help                 -> mostra ajuda rapida",
                "- sair                 -> encerra",
                "",
                "Dica: cole uma frase com URL do GitHub e o sistema indexa automaticamente.",
                "Perguntas normais usam o repositorio ativo como contexto.",
            ]
        ),
        f"{TermColors.BOLD}{TermColors.MAGENTA}",
    )


def get_api_key() -> str | None:
    api_key = os.getenv("XAI_API_KEY")
    if api_key:
        return api_key

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                value, _ = winreg.QueryValueEx(key, "XAI_API_KEY")
                return value
        except OSError:
            return None

    return None


def ensure_dirs() -> None:
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


def repo_id_from_url(repo_url: str) -> str:
    clean = repo_url.strip().rstrip("/")
    if clean.endswith(".git"):
        clean = clean[:-4]
    parts = clean.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}_{parts[-1]}".lower()
    return re.sub(r"[^a-zA-Z0-9_-]", "_", clean).lower()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def read_text_file(file_path: Path) -> str | None:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return file_path.read_text(encoding="latin-1")
        except OSError:
            return None
    except OSError:
        return None


def chunk_lines(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap_lines: int = CHUNK_OVERLAP_LINES) -> list[tuple[str, int, int]]:
    lines = text.splitlines()
    if not lines:
        return []

    chunks: list[tuple[str, int, int]] = []
    buffer: list[tuple[int, str]] = []
    current_chars = 0

    for line_no, line in enumerate(lines, start=1):
        line_with_newline = f"{line}\n"
        if buffer and current_chars + len(line_with_newline) > max_chars:
            start_line = buffer[0][0]
            end_line = buffer[-1][0]
            content = "".join(item[1] for item in buffer).strip()
            if content:
                chunks.append((content, start_line, end_line))

            overlap = buffer[-overlap_lines:] if overlap_lines > 0 else []
            buffer = list(overlap)
            current_chars = sum(len(item[1]) for item in buffer)

        buffer.append((line_no, line_with_newline))
        current_chars += len(line_with_newline)

    if buffer:
        start_line = buffer[0][0]
        end_line = buffer[-1][0]
        content = "".join(item[1] for item in buffer).strip()
        if content:
            chunks.append((content, start_line, end_line))

    return chunks


def file_type_label(file_path: Path) -> str:
    name_lower = file_path.name.lower()
    if name_lower in SUPPORTED_FILENAMES:
        return name_lower
    suffix = file_path.suffix.lower()
    if suffix:
        return suffix
    if name_lower.startswith("readme"):
        return "readme"
    return "<sem_extensao>"


def is_supported_file(file_path: Path) -> bool:
    name_lower = file_path.name.lower()
    suffix = file_path.suffix.lower()
    return (
        name_lower in SUPPORTED_FILENAMES
        or name_lower.startswith("readme")
        or suffix in SUPPORTED_EXTENSIONS
    )


def iter_repo_files(repo_path: Path) -> tuple[list[Path], dict]:
    files: list[Path] = []
    skipped_reasons: Counter[str] = Counter()
    by_type: dict[str, dict[str, int]] = {}

    def bump_file_type(file_type: str, key: str) -> None:
        data = by_type.setdefault(
            file_type,
            {"vistos": 0, "candidatos": 0, "indexados": 0, "ignorados": 0},
        )
        data[key] += 1

    total_seen = 0
    skipped_dirs = 0

    for root, dirs, filenames in os.walk(repo_path):
        original_dir_count = len(dirs)
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        skipped_dirs += max(0, original_dir_count - len(dirs))

        root_path = Path(root)
        for name in filenames:
            total_seen += 1
            file_path = root_path / name
            kind = file_type_label(file_path)
            bump_file_type(kind, "vistos")

            if not is_supported_file(file_path):
                skipped_reasons["extensao_nao_suportada"] += 1
                bump_file_type(kind, "ignorados")
                continue

            try:
                if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                    skipped_reasons["arquivo_muito_grande"] += 1
                    bump_file_type(kind, "ignorados")
                    continue
            except OSError:
                skipped_reasons["falha_stat_arquivo"] += 1
                bump_file_type(kind, "ignorados")
                continue

            files.append(file_path)
            bump_file_type(kind, "candidatos")

    coverage = {
        "total_arquivos_vistos": total_seen,
        "pastas_ignoradas": skipped_dirs,
        "arquivos_candidatos": len(files),
        "arquivos_indexados": 0,
        "arquivos_ignorados_por_motivo": dict(skipped_reasons),
        "por_tipo": by_type,
    }
    return files, coverage


def mark_coverage_indexed_file(coverage: dict, file_path: Path) -> None:
    file_type = file_type_label(file_path)
    type_stats = coverage.get("por_tipo", {}).setdefault(
        file_type,
        {"vistos": 0, "candidatos": 0, "indexados": 0, "ignorados": 0},
    )
    type_stats["indexados"] += 1
    coverage["arquivos_indexados"] = int(coverage.get("arquivos_indexados", 0)) + 1


def mark_coverage_skipped(coverage: dict, file_path: Path, reason: str) -> None:
    ignored = Counter(coverage.get("arquivos_ignorados_por_motivo", {}))
    ignored[reason] += 1
    coverage["arquivos_ignorados_por_motivo"] = dict(ignored)

    file_type = file_type_label(file_path)
    type_stats = coverage.get("por_tipo", {}).setdefault(
        file_type,
        {"vistos": 0, "candidatos": 0, "indexados": 0, "ignorados": 0},
    )
    type_stats["ignorados"] += 1


def summarize_coverage(coverage: dict) -> str:
    ignored = coverage.get("arquivos_ignorados_por_motivo", {})
    ignored_sorted = sorted(ignored.items(), key=lambda item: item[1], reverse=True)
    ignored_text = ", ".join(f"{reason}={count}" for reason, count in ignored_sorted[:5])
    if not ignored_text:
        ignored_text = "nenhum"

    return (
        f"vistos={coverage.get('total_arquivos_vistos', 0)}, "
        f"candidatos={coverage.get('arquivos_candidatos', 0)}, "
        f"indexados={coverage.get('arquivos_indexados', 0)}, "
        f"pastas_ignoradas={coverage.get('pastas_ignoradas', 0)}, "
        f"ignorados_top={ignored_text}"
    )


def bm25_score(query_tokens: list[str], doc_tf: dict[str, int], doc_len: int, avg_doc_len: float, df: dict[str, int], n_docs: int) -> float:
    if not query_tokens or not doc_tf:
        return 0.0

    k1 = 1.5
    b = 0.75
    score = 0.0
    for term in set(query_tokens):
        tf = doc_tf.get(term, 0)
        if tf == 0:
            continue
        term_df = df.get(term, 0)
        idf = math.log(1 + (n_docs - term_df + 0.5) / (term_df + 0.5))
        denom = tf + k1 * (1 - b + b * (doc_len / max(avg_doc_len, 1e-9)))
        score += idf * ((tf * (k1 + 1)) / denom)
    return score


def save_index(index_data: dict) -> Path:
    index_path = INDEX_DIR / f"{index_data['repo_id']}.json"
    index_path.write_text(json.dumps(index_data, ensure_ascii=False), encoding="utf-8")
    return index_path


def load_index(repo_id: str) -> dict | None:
    path = INDEX_DIR / f"{repo_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_indexed_repos() -> list[dict]:
    repos: list[dict] = []
    for path in sorted(INDEX_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            repos.append(
                {
                    "repo_id": data.get("repo_id"),
                    "repo_url": data.get("repo_url"),
                    "chunks": len(data.get("chunks", [])),
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    return repos


def clone_or_update_repo(repo_url: str) -> tuple[str, Path]:
    repo_id = repo_id_from_url(repo_url)
    destination = REPOS_DIR / repo_id

    if destination.exists():
        result = subprocess.run(
            ["git", "-C", str(destination), "pull", "--ff-only"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Falha ao atualizar o repositorio. "
                f"Detalhe: {result.stderr.strip() or result.stdout.strip()}"
            )
        return repo_id, destination

    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(destination)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Falha ao clonar o repositorio. "
            f"Detalhe: {result.stderr.strip() or result.stdout.strip()}"
        )
    return repo_id, destination


def ingest_repo(repo_url: str) -> dict:
    repo_id, repo_path = clone_or_update_repo(repo_url)
    files, coverage = iter_repo_files(repo_path)

    chunks: list[dict] = []
    df_counter: Counter[str] = Counter()
    files_processed = 0

    for file_path in files:
        text = read_text_file(file_path)
        if not text:
            mark_coverage_skipped(coverage, file_path, "arquivo_nao_textual_ou_inlegivel")
            continue
        relative = file_path.relative_to(repo_path).as_posix()
        line_chunks = chunk_lines(text)
        if not line_chunks:
            mark_coverage_skipped(coverage, file_path, "sem_conteudo_util_apos_chunk")
            continue

        files_processed += 1
        mark_coverage_indexed_file(coverage, file_path)
        for content, start_line, end_line in line_chunks:
            tf_counter = Counter(tokenize(content))
            if not tf_counter:
                continue
            df_counter.update(tf_counter.keys())
            chunks.append(
                {
                    "path": relative,
                    "start_line": start_line,
                    "end_line": end_line,
                    "content": content,
                    "tf": dict(tf_counter),
                    "length": int(sum(tf_counter.values())),
                }
            )

    avg_doc_len = (
        sum(chunk["length"] for chunk in chunks) / len(chunks)
        if chunks
        else 0.0
    )

    index_data = {
        "repo_id": repo_id,
        "repo_url": repo_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files_processed": files_processed,
        "coverage": coverage,
        "chunks": chunks,
        "df": dict(df_counter),
        "avg_doc_len": avg_doc_len,
    }
    save_index(index_data)
    return index_data


def retrieve_chunks(index_data: dict, question: str, top_k: int = TOP_K) -> list[dict]:
    chunks = index_data.get("chunks", [])
    if not chunks:
        return []

    query_tokens = tokenize(question)
    if not query_tokens:
        return []

    df = index_data.get("df", {})
    avg_doc_len = index_data.get("avg_doc_len", 0.0)
    n_docs = len(chunks)

    scored: list[tuple[float, dict]] = []
    for chunk in chunks:
        score = bm25_score(
            query_tokens=query_tokens,
            doc_tf=chunk.get("tf", {}),
            doc_len=chunk.get("length", 0),
            avg_doc_len=avg_doc_len,
            df=df,
            n_docs=n_docs,
        )
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:top_k]]


def build_context(chunks: list[dict]) -> str:
    if not chunks:
        return "Nenhum trecho relevante encontrado no repositorio indexado."

    parts: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        parts.append(
            (
                f"[{idx}] {chunk['path']}:{chunk['start_line']}-{chunk['end_line']}\n"
                f"{chunk['content']}"
            )
        )
    return "\n\n".join(parts)


def extract_github_repo_url(text: str) -> str | None:
    match = GITHUB_REPO_URL_PATTERN.search(text)
    if not match:
        return None

    url = match.group(1).strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"https://{url}"
    return url


def extract_question_without_url(text: str, repo_url: str) -> str:
    question = re.sub(re.escape(repo_url), "", text, flags=re.IGNORECASE)
    question = question.strip().strip('"\'')

    # Remove frases comuns de "pedido de acesso" para sobrar apenas a intencao.
    prefixes = [
        r"^acesse\s+(esse|este|o)?\s*repositorio\s*(do github)?\s*",
        r"^analise\s+(esse|este|o)?\s*repositorio\s*",
        r"^use\s+(esse|este|o)?\s*repositorio\s*",
    ]
    for prefix in prefixes:
        question = re.sub(prefix, "", question, flags=re.IGNORECASE).strip(" .,:;-")

    connector_prefixes = [
        r"^(e\s+)?fa[çc]a\s+",
        r"^(e\s+)?me\s+mostre\s+",
        r"^(e\s+)?me\s+explique\s+",
    ]
    for prefix in connector_prefixes:
        question = re.sub(prefix, "", question, flags=re.IGNORECASE).strip(" .,:;-")

    return question


api_key = get_api_key()
if not api_key:
    raise ValueError("Defina a variavel de ambiente XAI_API_KEY antes de executar.")

ensure_dirs()
enable_windows_ansi()

client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

print_banner()

active_repo_id: str | None = None
active_index: dict | None = None

while True:
    user_input = input(f"{TermColors.BOLD}{TermColors.CYAN}Voce > {TermColors.RESET}").strip()
    if user_input.lower() == "sair":
        print_system_message("Encerrando o chat. Ate mais!")
        break
    if not user_input:
        continue

    print_user_message(user_input)

    if user_input.lower().startswith("ingest "):
        repo_url = user_input[7:].strip()
        if not repo_url:
            print_error_message("Informe a URL do repositorio.")
            continue
        try:
            print_system_message("Indexando repositorio... isso pode levar alguns minutos.")
            active_index = ingest_repo(repo_url)
            active_repo_id = active_index["repo_id"]
            print_system_message(
                "Indexacao concluida! "
                f"repo_id={active_repo_id}, "
                f"arquivos={active_index['files_processed']}, "
                f"chunks={len(active_index['chunks'])}.\n"
                f"Cobertura: {summarize_coverage(active_index.get('coverage', {}))}"
            )
        except Exception as exc:
            print_error_message(f"Falha na ingestao: {exc}")
        continue

    if user_input.lower() == "repos":
        repos = list_indexed_repos()
        if not repos:
            print_system_message("Nenhum repositorio indexado ainda.")
            continue
        lines = ["Repositorios indexados:"]
        for repo in repos:
            marker = " (ativo)" if repo["repo_id"] == active_repo_id else ""
            lines.append(
                f"- {repo['repo_id']} | chunks={repo['chunks']} | url={repo['repo_url']}{marker}"
            )
        print_system_message("\n".join(lines))
        continue

    if user_input.lower().startswith("use "):
        repo_id = user_input[4:].strip().lower()
        if not repo_id:
            print_error_message("Informe o repo_id.")
            continue
        loaded = load_index(repo_id)
        if not loaded:
            print_error_message("Repo nao encontrado no indice local. Use 'repos' para listar.")
            continue
        active_repo_id = repo_id
        active_index = loaded
        print_system_message(f"Repositorio ativo: {active_repo_id}")
        continue

    if user_input.lower() == "coverage":
        if not active_index:
            print_error_message("Nenhum repositorio ativo. Use 'ingest <url>' ou 'use <repo_id>'.")
            continue
        coverage = active_index.get("coverage", {})
        if not coverage:
            print_system_message(
                "Este indice nao possui dados de cobertura (provavelmente gerado em versao anterior)."
            )
            continue

        top_types = sorted(
            coverage.get("por_tipo", {}).items(),
            key=lambda item: item[1].get("indexados", 0),
            reverse=True,
        )[:10]
        lines = [
            "Cobertura do repositorio ativo:",
            summarize_coverage(coverage),
            "",
            "Top tipos por arquivos indexados:",
        ]
        for file_type, stats in top_types:
            lines.append(
                f"- {file_type}: vistos={stats.get('vistos', 0)}, "
                f"candidatos={stats.get('candidatos', 0)}, "
                f"indexados={stats.get('indexados', 0)}, "
                f"ignorados={stats.get('ignorados', 0)}"
            )
        print_system_message("\n".join(lines))
        continue

    if user_input.lower() == "help":
        print_system_message(
            "\n".join(
                [
                    "Comandos: ingest <url_github>, repos, use <repo_id>, coverage, help, sair.",
                    "",
                    "Exemplo natural:",
                    "Acesse https://github.com/owner/repo e me explique a arquitetura.",
                ]
            )
        )
        continue

    inferred_repo_url = extract_github_repo_url(user_input)
    if inferred_repo_url:
        try:
            print_system_message("URL de repositorio detectada. Iniciando ingestao automatica...")
            active_index = ingest_repo(inferred_repo_url)
            active_repo_id = active_index["repo_id"]
            print_system_message(
                "Repositorio pronto para consulta! "
                f"repo_id={active_repo_id}, "
                f"arquivos={active_index['files_processed']}, "
                f"chunks={len(active_index['chunks'])}.\n"
                f"Cobertura: {summarize_coverage(active_index.get('coverage', {}))}"
            )
        except Exception as exc:
            print_error_message(f"Falha na ingestao automatica: {exc}")
            continue

        remaining_question = extract_question_without_url(user_input, inferred_repo_url)
        if not remaining_question:
            print_system_message("Agora faca sua pergunta sobre esse repositorio.")
            continue

        print_system_message(f"Pergunta interpretada: {remaining_question}")
        user_input = remaining_question

    if not active_index:
        response = client.chat.completions.create(
            model="grok-4-1-fast",
            messages=[{"role": "user", "content": user_input}],
        )
        print_agent_message(response.choices[0].message.content or "Sem conteudo retornado.")
        continue

    retrieved = retrieve_chunks(active_index, user_input, top_k=TOP_K)
    context_text = build_context(retrieved)
    prompt = (
        "Voce e um agente de analise de repositorios. "
        "Use o contexto recuperado para responder com foco tecnico e acao objetiva.\n\n"
        "Formato da resposta:\n"
        "1) Resumo objetivo\n"
        "2) Evidencias (arquivos/linhas)\n"
        "3) Estrutura do pedido final recomendado ao time\n"
        "4) Proximos passos\n\n"
        f"Pergunta do usuario:\n{user_input}\n\n"
        f"Contexto recuperado do repositorio ({active_repo_id}):\n{context_text}"
    )

    response = client.chat.completions.create(
        model="grok-4-1-fast",
        messages=[{"role": "user", "content": prompt}],
    )

    print_agent_message(response.choices[0].message.content or "Sem conteudo retornado.")