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
