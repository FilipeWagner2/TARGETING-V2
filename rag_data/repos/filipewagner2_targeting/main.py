import os
from dotenv import load_dotenv
from openai import AuthenticationError, RateLimitError, APIError
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Carregar variáveis de ambiente do arquivo .env (sobrescrevendo variáveis já definidas)
load_dotenv(override=True)

# Validar se a chave da OpenAI foi configurada corretamente antes de criar o cliente
openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
if not openai_api_key or openai_api_key == "sk-sua-chave-aqui":
  raise RuntimeError(
    "OPENAI_API_KEY não configurada corretamente. Atualize o arquivo .env com sua chave real."
  )

# Inicializar o LLM (Language Model) com GPT-4o-mini
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2
)

# Criar o template de prompt com mensagens de sistema e usuário
prompt = ChatPromptTemplate.from_messages([
    ("system", "Você é um Engenheiro de Software Sênior especialista em analisar, refatorar e adaptar projetos de código."),
    ("user", "Analise o seguinte projeto base e adapte para o que eu pedir.\n\nPROJETO ORIGINAL:\n{projeto_original}\n\nO QUE EU QUERO:\n{pedido_usuario}")
])

# Criar a chain unindo o prompt e o llm usando pipe
chain = prompt | llm

# Dados simulados para teste
projeto_original = """
// index.js - Sistema de Cadastro (tudo junto e bagunçado)
const express = require('express');
const mysql = require('mysql');
const app = express();

const connection = mysql.createConnection({
  host: 'localhost',
  user: 'root',
  password: '12345',
  database: 'cadastros'
});

app.use(express.json());

let usuarios = [];

app.post('/adduser', (req, res) => {
  const { nome, email, idade } = req.body;
  usuarios.push({ id: Math.random(), nome, email, idade });
  connection.query('INSERT INTO users (nome, email, idade) VALUES (?, ?, ?)', 
    [nome, email, idade], 
    (err, result) => {
      if (err) res.json({ erro: err });
      else res.json({ sucesso: true, id: result.insertId });
    }
  );
});

app.get('/users', (req, res) => {
  connection.query('SELECT * FROM users', (err, results) => {
    if (err) res.json({ erro: err });
    else res.json(results);
  });
});

app.listen(3000, () => console.log('Servidor rodando na porta 3000'));
"""

pedido_usuario = "Transformar a ideia desse projeto em uma API REST profissional usando Python e FastAPI, separando as rotas e explicando a estrutura de pastas"

# Executar a chain passando as variáveis
print("=" * 80)
print("🤖 AI CODE AGENT - MVP LangChain")
print("=" * 80)
print("\n⏳ Processando solicitação...\n")

try:
  response = chain.invoke({
    "projeto_original": projeto_original,
    "pedido_usuario": pedido_usuario
  })

  # Exibir resposta formatada
  print("📋 RESPOSTA DO AGENTE:")
  print("-" * 80)
  print(response.content)
  print("-" * 80)
except AuthenticationError:
  print("Erro de autenticação: verifique se a OPENAI_API_KEY no .env está válida.")
except RateLimitError:
  print("Erro de quota/limite da API: sua conta OpenAI está sem saldo ou excedeu o limite atual.")
  print("Ação recomendada: revisar billing/usage no painel da OpenAI e tentar novamente.")
except APIError as exc:
  print(f"Erro de API OpenAI: {exc}")
