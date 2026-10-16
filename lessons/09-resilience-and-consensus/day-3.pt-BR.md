# Módulo 9, quarta-feira: disaster recovery, migrações seguras e feature flags

[Módulo 9](../../modules/09-resilience-and-consensus.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Segunda e terça foram sobre sobreviver a minutos ruins: um parceiro lento, um pico de tráfego, um nó que morre. Hoje o assunto são duas outras formas de uma carteira digital perder dinheiro e confiança. A primeira é o dia ruim: uma região apaga, ou alguém roda um `DELETE` sem `WHERE`. A segunda é autoinfligida: um deploy ou uma migração de schema que quebra a produção. Reguladores e bancos parceiros vão perguntar quanto tempo você pode ficar fora do ar e quantos dados pode perder. Você precisa de números, e precisa tê-los testado.

O TCM de sexta pede exatamente isso: um backup e restore por script, um `docs/m09.md` com seu RPO e RTO, e uma renomeação de coluna sem downtime. O lab de hoje é a preparação.

## 1. RPO e RTO

*Fonte principal: whitepaper da AWS "Disaster Recovery of Workloads on AWS", página "Disaster recovery options in the cloud".*

Dois números descrevem qualquer plano de recuperação. O whitepaper os usa do começo ao fim como as metas que cada estratégia precisa cumprir:

- **RPO (recovery point objective):** o máximo de dados, medido em tempo, que você aceita perder. Um RPO de 5 minutos significa que, depois de um desastre, você pode perder até os últimos 5 minutos de escritas.
- **RTO (recovery time objective):** o máximo de tempo que você aceita ficar fora do ar, do momento do desastre até o serviço voltar a funcionar.

São decisões de negócio, não técnicas, e variam por tipo de dado:

| Dado | Meta razoável | Por quê |
| --- | --- | --- |
| Lançamentos do ledger e transferências | RPO perto de zero, RTO em minutos | Um lançamento perdido significa um saldo que não bate com o banco parceiro |
| Idempotency keys | O mesmo do ledger | Perdê-las permite que um retry cobre duas vezes |
| Histórico de notificações push | RPO de horas | Chato de perder, não perigoso |
| Data warehouse de analytics | RPO e RTO de um dia | Pode ser reconstruído a partir do ledger |

Um ponto importante do whitepaper: a replicação contínua dá um RPO baixo contra a perda de um site, mas não protege contra **corrupção de dados ou exclusão maliciosa**, porque a alteração ruim também é replicada. Para isso você precisa de **backups point-in-time**. Uma carteira digital precisa dos dois: replicação para o caso "a região sumiu", e backups para o caso "alguém apagou as linhas erradas".

## 2. Quatro estratégias, da mais barata à mais cara

*Fonte principal: whitepaper da AWS, "Disaster recovery options in the cloud".*

O whitepaper agrupa as estratégias em quatro, ordenadas por custo e complexidade. Ele descreve o RPO e o RTO de cada uma em termos relativos; não dá números fixos nesta página.

| Estratégia | O que roda no site de recuperação | Recuperação |
| --- | --- | --- |
| **Backup and restore** | Só os backups | Restaurar os dados e reimplantar toda a infraestrutura. A mais lenta e a mais barata. |
| **Pilot light** | Dados replicados continuamente; serviços centrais como bancos de dados ligados; servidores de aplicação definidos, mas desligados | Ligar e escalar os servidores de aplicação. Mais rápida. |
| **Warm standby** | Uma cópia menor, mas totalmente funcional, da produção | Escalá-la. Mais rápida ainda. |
| **Multi-site active/active** | A produção completa, atendendo tráfego | Não há passo de failover: o tráfego é desviado do site que falhou. |

As três primeiras são **ativo-passivo**: o site passivo não atende tráfego até um failover. Só o ativo-ativo atende usuários a partir de todos os sites.

Detalhes do whitepaper que importam para o seu design:

- **Infraestrutura como código.** Backup and restore só cumpre o RTO se você conseguir recriar o ambiente rápido e sem erros manuais.
- **Cuidado com failover automático.** O whitepaper alerta que fazer failover automaticamente com base em health checks pode transformar um alarme falso em uma queda real. Ele recomenda que até o failover manual seja automatizado, para ser uma ação única e testada.
- **Teste o plano.** Um backup que você nunca restaurou é uma esperança, não um backup. Escalar um warm standby também depende de operações de plano de controle (como auto scaling) que podem estar degradadas durante um evento regional, e é por isso que algumas equipes provisionam a capacidade total com antecedência (um "hot standby").

No TCM, sua carteira digital roda em uma máquina com Docker Compose, então sua estratégia é backup and restore. Tudo bem. O que importa é que o RPO e o RTO no `docs/m09.md` venham de medição, não de chute.

## 3. Por que ativo-ativo com saldos é difícil

*Fonte principal: whitepaper da AWS, "Disaster recovery options in the cloud", seção sobre multi-site active/active. A análise da carteira digital é deste curso.*

Ativo-ativo parece ideal: RTO perto de zero, sem failover. O whitepaper explica que as leituras normalmente são atendidas localmente, e oferece três padrões para escritas:

- **Write global:** todas as escritas vão para uma região; se ela falhar, outra região é promovida.
- **Write local:** cada região aceita escritas, e atualizações concorrentes são reconciliadas, por exemplo com **last writer wins** (o whitepaper cita isso para as DynamoDB global tables).
- **Write partitioned:** cada registro tem uma região "dona", escolhida por uma chave como o ID do usuário, então duas regiões nunca escrevem o mesmo registro.

Agora aplique isso a um saldo. Alice tem R$ 100. No mesmo instante, ela paga R$ 80 em uma loja roteada para São Paulo e envia R$ 80 por Pix em uma requisição roteada para a Virgínia.

- Com **write local**, cada região consulta sua cópia local, vê R$ 100 e aprova. Depois da replicação, ela gastou R$ 160 de R$ 100. Last writer wins piora tudo: um dos dois lançamentos é sobrescrito em silêncio, e o ledger deixa de bater com o dinheiro que saiu.
- A verificação de saldo é um invariante sobre todas as escritas da conta ("nunca abaixo de zero"). Garanti-lo exige uma autoridade por conta a cada momento: um único líder, ou consenso entre regiões. Consenso entre continentes (o Raft de terça) significa que todo débito espera uma ida e volta até a maioria, de dezenas a centenas de milissegundos.
- **Write partitioned** é a resposta prática: cada conta tem uma região dona, onde acontecem todos os seus débitos. Mas uma transferência entre uma conta de São Paulo e uma da Virgínia passa a ser uma operação entre regiões, o que traz de volta sagas, outboxes e conciliação dos módulos anteriores.

Então a resposta honesta na entrevista é: ativo-ativo funciona bem para leituras e para dados sem invariantes entre registros. Para saldos, ou você roteia cada conta para um único escritor (particionamento), ou paga a latência do consenso em toda escrita. É por isso que muitos sistemas de pagamento escolhem ativo-passivo para o ledger, com RPO baixo graças a replicação síncrona ou quase síncrona, e aceitam um RTO de minutos.

## 4. Backup e restore com Postgres

*Fonte principal: documentação do PostgreSQL, capítulo "Backup and Restore".*

A documentação do PostgreSQL descreve três abordagens: SQL dump, backup no nível do sistema de arquivos e arquivamento contínuo. Duas delas importam aqui:

- **Backups lógicos** com `pg_dump`: um retrato dos dados e do schema em um momento, restaurável com `pg_restore`. Simples e portátil. Seu RPO é o tempo desde o último dump.
- **Backups físicos com arquivamento de WAL**: um backup base mais um arquivo contínuo do write-ahead log. Você pode reaplicar o log até qualquer instante, por exemplo até um segundo antes do `DELETE` errado. Isso é point-in-time recovery (PITR), e serviços gerenciados de Postgres costumam oferecê-lo como funcionalidade.

Para o TCM, um backup lógico basta. O formato do script:

```bash
#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
pg_dump --format=custom --file="backups/wallet-$STAMP.dump" "$DATABASE_URL"

# Restaure em um banco novo e cronometre: esse é o seu RTO medido.
time pg_restore --clean --if-exists --no-owner -d "$RESTORE_URL" "backups/wallet-$STAMP.dump"
```

Um restore só está "pronto" depois de verificado. Para um ledger, as verificações mínimas são a contagem de linhas por tabela e o invariante de que os lançamentos de cada transferência somam zero:

```sql
-- Não pode retornar nenhuma linha depois de um restore.
SELECT transfer_id, SUM(amount_cents) AS imbalance
FROM ledger_entries
GROUP BY transfer_id
HAVING SUM(amount_cents) <> 0;
```

Anote três números no `docs/m09.md`: a frequência do backup (seu RPO), quanto tempo levaram o restore e as verificações (seu RTO) e o tamanho do dump.

## 5. Parallel change: migrações sem downtime

*Fonte principal: Danilo Sato, "Parallel Change", bliki do martinfowler.com, 2014.*

Durante um rolling deploy, versões antigas e novas do seu código rodam ao mesmo tempo, contra o mesmo banco. Então uma mudança de schema que o código antigo não entende quebra a produção enquanto durar o deploy. Renomear uma coluna em uma única migração é o exemplo clássico: no momento em que o `ALTER TABLE ... RENAME COLUMN` faz commit, as queries de todos os pods antigos falham.

Sato descreve o **parallel change**, também chamado de **expand and contract**, como uma forma de fazer uma mudança incompatível em três passos seguros. Ele observa que a técnica foi documentada pela primeira vez como estratégia de refatoração por Joshua Kerievsky em 2006, e que a maioria das refatorações de banco de dados segue esse padrão.

1. **Expand:** acrescente a versão nova ao lado da antiga. Os clientes antigos continuam funcionando.
2. **Migrate:** mova os clientes para a versão nova, passo a passo. Durante essa fase, as duas versões precisam funcionar.
3. **Contract:** quando ninguém mais usa a versão antiga, remova-a.

Sato também alerta que pular a fase de contract deixa o código pior do que antes, com duas versões de tudo. Coloque o passo de contract no backlog no dia em que fizer o expand.

Aqui está o cenário do TCM de sexta em esboço: renomear `transfers.ext_ref` para `transfers.partner_reference`.

| Passo | Banco de dados | Aplicação |
| --- | --- | --- |
| 1. Expand | Acrescentar a coluna `partner_reference`, anulável; acrescentar um trigger que copia escritas de uma coluna para a outra | Nada novo é implantado ainda |
| 2. Backfill | Copiar as linhas antigas em lotes pequenos | Sem mudança |
| 3. Migrar leituras e escritas | Constraints na coluna nova | Implantar código que lê e escreve só `partner_reference` |
| 4. Contract | Remover o trigger, depois remover `ext_ref` | Só depois que todos os pods antigos saírem |

O SQL dos passos de expand e backfill fica assim:

```sql
-- Expand: acrescentar uma coluna anulável sem default é uma mudança rápida no catálogo.
ALTER TABLE transfers ADD COLUMN partner_reference text;

-- Backfill em lotes para evitar locks longos e transações enormes.
UPDATE transfers SET partner_reference = ext_ref
WHERE id IN (
  SELECT id FROM transfers
  WHERE partner_reference IS NULL AND ext_ref IS NOT NULL
  LIMIT 5000
);
-- repita até 0 linhas atualizadas
```

Cada passo é um deploy próprio, e cada um pode ser revertido isoladamente. Esse é o ponto: nunca existe um momento em que o código em execução e o schema discordam. Você vai projetar o trigger e os passos de constraint por conta própria na sexta.

## 6. Feature toggles e canary releases

*Fonte principal: Pete Hodgson, "Feature Toggles (aka Feature Flags)", martinfowler.com, 2016 (revisado em 2017).*

O parallel change separa mudanças de schema de mudanças de código. As **feature toggles** separam implantar código de liberar comportamento. O código de uma nova rota de banco parceiro pode ficar em produção por uma semana, desligado, e ser ligado para 1% dos clientes quando você estiver pronto.

Hodgson dá nome às partes: um **toggle point** é o lugar no código que escolhe entre dois caminhos; um **toggle router** decide qual caminho está ativo, usando a **toggle configuration** e às vezes um **contexto**, como o ID do usuário. Depois ele classifica as toggles por quanto tempo vivem e por quão dinâmica é a decisão:

| Categoria | Objetivo | Duração | Decisão | Exemplo na carteira digital |
| --- | --- | --- | --- | --- |
| **Release** | Colocar código inacabado em produção desligado | Dias a semanas | Estática por release | Nova tela de extrato |
| **Experiment** | Testes A/B | O suficiente para ter estatística | Por requisição, estável por usuário | Dois fluxos de onboarding |
| **Ops** | Controlar comportamento operacional | Quase sempre curta; algumas permanentes | Alterada rápido em tempo de execução | Desligar o PDF de extrato no pico de carga |
| **Permissioning** | Funcionalidades para usuários específicos | Pode durar anos | Por requisição | Limites maiores para contas empresariais verificadas |

Duas ideias do artigo amarram este módulo:

- **Kill switches.** Hodgson descreve ops toggles de longa duração que funcionam como um circuit breaker operado à mão: durante um incidente, um operador desliga uma funcionalidade não essencial para poupar capacidade. É o load shedding de terça, feito por uma pessoa.
- **Canary releasing.** Ligue uma funcionalidade para uma pequena coorte aleatória (o exemplo dele seleciona 1% dos usuários por um módulo do ID do usuário), compare métricas de negócio com o resto e amplie só se os números parecerem bons. Hodgson diferencia isso de expor uma funcionalidade primeiro aos usuários internos, que mira um grupo escolhido e não uma amostra aleatória.

Um toggle router com rollout percentual estável poderia ser assim:

```typescript
import { createHash } from 'node:crypto';

function inRollout(flag: string, userId: string, percent: number): boolean {
  // Hash de flag + usuário para que cada flag tenha 1% independente e estável dos usuários.
  const h = createHash('sha256').update(`${flag}:${userId}`).digest();
  return h.readUInt32BE(0) % 100 < percent;
}

// Toggle point, mantido em um só lugar (Hodgson: separar pontos de decisão da lógica de decisão).
const route = inRollout('partner-bank-v2', user.id, config.partnerV2Percent)
  ? partnerBankV2
  : partnerBankV1;
```

Hodgson também enfatiza que toggles têm um **custo de manutenção** (carrying cost): caminhos de código extras, testes extras, confusão extra. Ele recomenda tratá-las como estoque a ser mantido pequeno: crie uma tarefa de remoção ao criar uma release toggle, defina datas de expiração e até acrescente testes que falham depois da expiração de uma toggle. Ele cita o caro incidente da Knight Capital como alerta sobre toggles antigas esquecidas no código. Em uma carteira digital, uma toggle esquecida que roteia alguns clientes para um parceiro desativado é um incidente de conciliação esperando para acontecer.

## 7. Juntando tudo para sexta

*Esta seção liga as três fontes às tarefas do TCM.*

Os itens 4 a 6 de sexta usam tudo de hoje:

- **k6 antes e depois (item 4).** Sua rodada "depois" só tem sentido se as proteções de segunda e terça puderem ser ligadas e desligadas. Ops toggles para o breaker e o rate limiter deixam a comparação limpa.
- **Renomeação com expand/contract (item 5).** Rode o k6 durante a migração. Se a taxa de erro ficar estável em todos os passos, você provou "sem downtime".
- **Backup e restore (item 6).** Meça o restore, rode as verificações do ledger e registre RPO e RTO no `docs/m09.md`, com um parágrafo sobre o que seria preciso para um RPO menor (arquivamento de WAL, uma réplica) e por que você não escolheu ativo-ativo para saldos.

Lab de hoje: escreva o script de backup, escolha o cenário de migração e liste os passos de quinta e sexta como tarefas. Ainda sem código do TCM.

## O que anotar hoje

1. RPO e RTO em uma frase cada, as quatro estratégias de DR em uma linha cada, e a diferença entre ativo-passivo e ativo-ativo.
2. Por que ativo-ativo com saldos é difícil: o gasto duplo em duas regiões, por que last writer wins perde lançamentos e quanto custa o write partitioning.
3. Os três passos do expand/contract, aplicados à sua renomeação de coluna, com o que é implantado em cada passo.
4. Os quatro tipos de feature toggle, o que é um kill switch e como funciona um canary release.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual a diferença entre RPO e RTO?
- Por que a replicação contínua não protege você de um `DELETE` errado?
- O que roda no site de recuperação em uma estratégia pilot light?
- Por que duas regiões não podem aceitar débitos da mesma conta só com verificações locais?
- Por que renomear uma coluna em uma única migração quebra um rolling deploy?
- Como um canary release difere de expor uma funcionalidade aos usuários internos?
- Qual é o custo de manutenção de uma feature toggle?

## Referências

- **Fonte principal:** whitepaper da AWS "Disaster Recovery of Workloads on AWS", página ["Disaster recovery options in the cloud"](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html). Leia as quatro estratégias e a parte sobre leituras e escritas em ativo-ativo. Gratuito.
- **Fonte principal:** Danilo Sato, ["Parallel Change"](https://martinfowler.com/bliki/ParallelChange.html), bliki do martinfowler.com, 2014. Curto; leia inteiro. Gratuito.
- **Fonte principal:** Pete Hodgson, ["Feature Toggles (aka Feature Flags)"](https://martinfowler.com/articles/feature-toggles.html), martinfowler.com, 2016, revisado em 2017. Leia as categorias de toggles, canary releasing e os conselhos sobre o custo de manutenção das toggles. Gratuito.
- Documentação do PostgreSQL, ["Backup and Restore"](https://www.postgresql.org/docs/current/backup.html). Leia a introdução do capítulo, "SQL Dump" e a visão geral de "Continuous Archiving and Point-in-Time Recovery (PITR)". Gratuito.
