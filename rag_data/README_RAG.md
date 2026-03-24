# O que e RAG e como ele funciona neste projeto

## O que e RAG
RAG significa Retrieval-Augmented Generation.

Em termos simples:
- Retrieval (recuperacao): o sistema busca trechos relevantes em uma base de conhecimento.
- Augmented Generation (geracao aumentada): o modelo responde usando esses trechos como contexto.

Sem RAG, o modelo responde apenas com conhecimento geral e o texto da conversa.
Com RAG, ele responde com base em evidencias reais de arquivos do repositorio.

## Por que usar RAG no seu caso
Seu objetivo e analisar repositorios e estruturar pedidos finais do usuario.

RAG ajuda porque:
- reduz respostas genericas;
- aumenta precisao tecnica;
- traz rastreabilidade (arquivo e linhas de onde veio a informacao);
- permite atualizar conhecimento apenas reindexando o repositorio, sem retreinar modelo.

## Como o RAG deste projeto foi aplicado
Fluxo implementado no teste.py:

1. Ingestao do repositorio
- Comando: ingest <url_github>
- O sistema clona (ou atualiza) o repo em rag_data/repos.

2. Leitura e recorte (chunking)
- Arquivos elegiveis sao lidos.
- Conteudo e quebrado em blocos (chunks) com metadados de caminho e linhas.

3. Indexacao local
- Os chunks sao indexados em rag_data/indexes.
- Tambem sao salvas estatisticas para busca (frequencia de termos).

4. Recuperacao para cada pergunta
- Ao receber uma pergunta, o sistema busca os chunks mais relevantes.
- Esses chunks viram contexto para o prompt enviado ao modelo.

5. Resposta estruturada
- O modelo responde com:
  - resumo objetivo;
  - evidencias (arquivos/linhas);
  - estrutura de pedido final recomendado;
  - proximos passos.

## Comandos disponiveis
- ingest <url_github>: clona/atualiza e indexa repositorio
- repos: lista repositorios indexados
- use <repo_id>: define repositorio ativo
- help: mostra ajuda
- sair: encerra

## Estrutura de pastas
- rag_data/repos: repositorios clonados
- rag_data/indexes: indices locais usados na recuperacao

## Limitacoes atuais
- Busca baseada principalmente em termos (lexical), nao embeddings semanticos.
- Arquivos muito grandes sao ignorados por seguranca/performance.
- Conteudo binario (imagens, PDFs sem extracao) nao entra no indice automaticamente.

## Evolucoes recomendadas
- Adicionar embeddings + vetor DB para busca semantica mais forte.
- Re-ranking dos trechos recuperados.
- Suporte nativo para PDF/DOCX (com extracao de texto).
- Modo multi-repositorio na mesma consulta.

## Resumo final
No seu projeto, RAG significa: usar o conteudo real dos repositorios como base das respostas.
Assim, o agente deixa de responder de forma generica e passa a responder com fundamento tecnico no codigo analisado.

## Novidades da V2
- Cobertura de ingestao ampliada: mais tipos de arquivos de codigo e configuracao entram como candidatos.
- Cobertura de ingestao ampliada para arquivos sem extensao comum (ex.: Jenkinsfile, Procfile e nomes customizados curtos).
- Relatorio de cobertura: o indice salva estatisticas de arquivos vistos, candidatos, indexados e ignorados por motivo.
- Entendimento estrutural explicito: o pipeline salva resumo estrutural com diretorios, linguagens, sinais de framework e entrypoints.
- Entendimento estrutural com camadas: o pipeline infere pistas de API, dominio, dados, testes e infraestrutura.
- Resposta padronizada: a saida final segue secoes fixas e consistentes.
- Adaptacao por intencao: classificacao simples de intencao ajusta profundidade de recuperacao e orientacao da resposta.

## Comandos V2
- ingest <url_github>: clona/atualiza e indexa repositorio
- repos: lista repositorios indexados
- use <repo_id>: define repositorio ativo
- coverage: mostra relatorio de cobertura do repositorio ativo
- structure: mostra resumo estrutural do repositorio ativo
- help: mostra ajuda
- sair: encerra

## Exemplo rapido de uso
1. Ingerir repositorio:
  ingest https://github.com/octocat/Hello-World
2. Ver cobertura:
  coverage
3. Ver estrutura:
  structure
4. Fazer pergunta:
  Explique a arquitetura e sugira proximos passos.

## Como validar localmente
1. Executar testes de regressao:
  python -m unittest discover -s tests -v
2. Executar fluxo CLI com comandos:
  python teste.py
3. Validar indice gerado em rag_data/indexes/<repo_id>.json:
  - campo coverage presente
  - campo structure presente

## Evidencias esperadas no indice
- coverage.total_arquivos_vistos
- coverage.arquivos_candidatos
- coverage.arquivos_indexados
- coverage.arquivos_ignorados_por_motivo
- structure.top_level_directories
- structure.languages
- structure.framework_signals
