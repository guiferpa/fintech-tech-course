[English](FLASHCARDS.md)

# Flashcards

O curso pede flashcards em três momentos: **10 minutos de revisão no começo de toda segunda**, **cards novos na entrega de sexta** (a partir do que faltou no teste de domínio gravado) e **uma revisão completa nas semanas de checkpoint**. Esta página mostra como montar tudo e como escrever cards que ajudam de verdade em entrevista.

## 1. Instale o Anki

Use o [Anki](https://apps.ankiweb.net/). Ele é gratuito no computador (Windows, macOS, Linux), na web ([AnkiWeb](https://ankiweb.net/)) e no Android ([AnkiDroid](https://play.google.com/store/apps/details?id=com.ichi2.anki)); o app de iOS é pago, e o AnkiWeb no navegador do celular é a alternativa gratuita. O Anki agenda cada card para logo antes de você esquecer (repetição espaçada), então 10 minutos por dia bastam.

1. Instale o Anki no computador e crie uma conta gratuita no AnkiWeb para sincronizar com o celular.
2. No Anki: **Ferramentas > Preferências > Revisão**, ative o **FSRS** (o agendador moderno, Anki 23.10+).
3. Crie o baralho **Fintech Tech Course** e um sub-baralho por módulo usando `::` no nome, por exemplo `Fintech Tech Course::M01 Fundamentos`, `Fintech Tech Course::M02 Idempotência` e assim por diante.
4. No baralho principal, abra as opções (ícone de engrenagem) e defina **Novos cards/dia** como 20 e **Máximo de revisões/dia** como 200.

## 2. Quando criar cards

| Momento | O que vira card | Quantos |
| --- | --- | --- |
| Leitura (seg a qua) | Ideias que você precisaria explicar numa entrevista: trade-offs, modos de falha, "por quê", números | 3 a 6 por sessão |
| Entrega de sexta | Ouça a gravação do teste de domínio. Cada lacuna, hesitação ou resposta errada vira um card | 5 a 10 |
| Checkpoints | O que faltou no simulado de system design, nos testes de domínio e no code review | Quantos precisar |

Escreva os cards você mesmo, com suas palavras. Escrever é metade do aprendizado; baralhos prontos que você não escreveu são esquecidos rápido.

## 3. Como escrever um bom card

- **Uma ideia por card.** Se a resposta é uma lista de 5 itens, divida ou use cloze.
- **Pergunte "por quê" e "e se", não só "o que é".** "Por que um timeout não pode virar FAILED?" ensina mais que "O que é timeout?".
- **Resposta curta, lembrada em poucos segundos.** Se precisa de um parágrafo, a pergunta está ampla demais.
- **Use cloze para listas e fórmulas.** No Anki, escolha o tipo de nota **Omissão de palavras (Cloze)** e marque a parte escondida assim: `{{c1::R + W > N}}`.
- **Cards de código: mostre o trecho e pergunte o que acontece.** É assim que entrevistas e code reviews cobram.
- **Marque a origem.** Use a tag do módulo (`m01`, `m02` ...) e `gap` nos cards que nasceram de um teste de domínio, para estudar os pontos fracos primeiro.

## 4. Exemplos

**Card básico** (Frente / Verso)

> **Frente:** A chamada ao banco parceiro dá timeout. Por que você não pode marcar a transferência como FAILED?
> **Verso:** A requisição pode ter sido processada. O desfecho é desconhecido: grave como UNKNOWN e reconcilie consultando o parceiro. Marcar FAILED e tentar de novo pode cobrar duas vezes.

> **Frente:** Contra o que uma chave de idempotência enviada pelo cliente protege, e contra o que não protege?
> **Verso:** Faz retries da mesma requisição devolverem o mesmo resultado. Não deduplica duas requisições diferentes com chaves diferentes, e a chave precisa ser gravada na mesma transação do efeito.

**Card de código**

> **Frente:** Duas sessões rodam isto ao mesmo tempo em READ COMMITTED. O que pode dar errado?
> ```sql
> SELECT balance FROM accounts WHERE id = 1;
> -- a aplicação calcula balance - 100
> UPDATE accounts SET balance = 900 WHERE id = 1;
> ```
> **Verso:** Lost update: as duas leem 1000 e as duas gravam 900, então um débito some. Corrija com `SELECT ... FOR UPDATE`, coluna de versão ou um `UPDATE ... SET balance = balance - 100 WHERE balance >= 100` condicional.

**Card cloze**

> Num sistema leaderless com N réplicas, uma leitura com certeza vê a última escrita quando `{{c1::R + W > N}}`.

> O padrão Outbox grava o evento `{{c1::na mesma transação do banco que a mudança de negócio}}` e o publica `{{c2::depois, a partir de um processo separado}}`.

## 5. Rotina

- **Segunda, primeiros 10 minutos da sessão:** revise todos os cards pendentes (a agenda lembra você).
- **Recomendado:** 5 minutos de cards pendentes no celular nos outros dias também. Pular um dia não tem problema; o Anki reagenda.
- **Como avaliar:** aperte **Errei** se não conseguiu explicar em voz alta e **Bom** se conseguiu. Seja rigoroso, é o único jeito do agendador funcionar.
- **Semanas de checkpoint:** use **Estudo personalizado > Revisar cards esquecidos** e estude a tag `gap` primeiro.

## 6. Opcional: importar cards de um arquivo

Se preferir escrever os cards num editor de texto, escreva um por linha num arquivo `.tsv` (frente, tab, verso, tab, tags) e importe em **Arquivo > Importar**, escolhendo o sub-baralho. O [`flashcards/template.tsv`](flashcards/template.tsv) traz os exemplos acima nesse formato.
