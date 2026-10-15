# Checkpoints

[Voltar para a ementa](../README.pt-BR.md) · [Read in English](checkpoints.md)

As semanas de checkpoint não têm conteúdo novo: um simulado de entrevista cronometrado, revisão do que ficou fraco e reposição de escopo cortado.

| Dia | Checkpoint 1 (semana 5, módulos 1 a 4) | Checkpoint 2 (semana 9, módulos 5 a 7) |
| --- | --- | --- |
| Seg | Revisar todos os flashcards; reler código e notas; listar escopo cortado | Igual |
| Ter | Repor escopo cortado, sem IA | Igual |
| Qua | System design de 45 min, gravado: **carteira digital** | System design de 45 min, gravado: **gateway de pagamento ou sistema de Pix** |
| Qui | 5 testes de domínio sorteados + code review de 30 min | Igual, para os módulos 5 a 7 |
| Sex | 3 respostas em inglês, 1 história STAR, 1 pergunta fora da sua experiência | Igual, e atualizar CV e LinkedIn |

**Aprovado se** cada gravação cobre falhas e idempotência sem você ser perguntado. O que faltou vira flashcard.

## Checklist de code review

Leia em voz alta antes de cada revisão:

1. Dinheiro em float?
2. Operação não idempotente com retry?
3. Leitura e escrita sem transação ou lock?
4. Chamada externa dentro de transação de banco?
5. Erro engolido, ou status desconhecido tratado como falha?
6. Segredo ou dado pessoal em log?
7. Falta de timeout?
8. (A partir do módulo 5) Consumidor sem dedupe?
9. (A partir do módulo 6) Lançamento que não fecha em zero?
