# Roteiro · M9 · Dia 3 · DR, migrações e feature toggles


## Abertura

Esta é a aula em vídeo do módulo nove, dia três: recuperação de desastre, migrações sem downtime e feature toggles.

Segunda e terça foram sobre sobreviver a minutos ruins. Hoje são duas outras formas de perder dinheiro e confiança. O dia ruim: uma região apaga, ou alguém roda um delete sem where. E o autoinfligido: um deploy ou uma migração que quebra a produção. Reguladores e bancos parceiros vão perguntar quanto tempo você pode ficar fora do ar e quantos dados pode perder. Você precisa de números, testados.


## RPO e RTO

Dois números descrevem qualquer plano de recuperação. O R P O é o máximo de dados, medido em tempo, que você aceita perder. Um R P O de cinco minutos: você pode perder os últimos cinco minutos de escritas. O R T O é o máximo de tempo fora do ar, do desastre até voltar. São decisões de negócio, e variam por dado.

Lançamentos do ledger e transferências: R P O perto de zero, R T O em minutos. Um lançamento perdido é um saldo que não bate com o banco parceiro.

Idempotency keys: o mesmo do ledger, porque perdê-las permite que um retry cobre duas vezes.

Histórico de notificações push: R P O de horas. Chato de perder, não perigoso.

Data warehouse de analytics: um dia, porque pode ser reconstruído do ledger.

E um ponto importante: a replicação contínua dá R P O baixo contra a perda de um site, mas não protege contra corrupção ou exclusão maliciosa, porque a alteração ruim também é replicada. Para isso, backups point-in-time. Uma carteira precisa dos dois.

> **Pausa:** Pergunta: por que uma réplica síncrona não salva você de um delete sem where?

Porque o delete também é replicado, na hora. Só um backup point-in-time permite voltar a antes do erro.


## Quatro estratégias

O whitepaper de recuperação de desastre da A W S agrupa as estratégias em quatro, por custo e complexidade.

Backup and restore: só os backups no site de recuperação. Você restaura os dados e reimplanta toda a infraestrutura. A mais lenta, e a mais barata. Só cumpre o R T O com infraestrutura como código.

Pilot light: os dados são replicados continuamente, e os bancos ficam ligados. Os servidores de aplicação estão definidos, mas desligados. Você liga e escala.

Warm standby: uma cópia menor, mas totalmente funcional. Você só escala.

E multi site active active: a produção completa atendendo tráfego em todos os sites. Não há failover, o tráfego só é desviado. As três primeiras são ativo-passivo.

Dois alertas. Failover automático por health check pode transformar um alarme falso numa queda real, então automatize até o failover manual, como uma ação única e testada. E um backup que você nunca restaurou é uma esperança, não um backup. No projeto, a carteira roda em Docker Compose, então a estratégia é backup and restore. O que importa é que os números venham de medição.


## Ativo-ativo com saldos

Ativo-ativo parece ideal: R T O perto de zero. As leituras são locais. Para escritas, há três padrões: write global, uma região recebe tudo. Write local, cada região aceita e reconcilia depois. E write partitioned, cada registro tem uma região dona. Agora aplique a um saldo.

Alice tem cem reais. No mesmo instante, paga oitenta numa loja roteada para São Paulo, e envia oitenta por Pix roteado para a Virgínia.

Com write local, cada região consulta a sua cópia, vê cem, e aprova. Depois da replicação, ela gastou cento e sessenta de cem.

Last writer wins piora: um dos lançamentos é sobrescrito em silêncio, e o ledger deixa de bater com o dinheiro que saiu.

O saldo nunca negativo é um invariante sobre todas as escritas da conta. Garanti-lo exige uma autoridade por conta: um líder, ou consenso entre regiões. Consenso entre continentes significa que todo débito espera uma ida e volta até a maioria, dezenas a centenas de milissegundos.

A resposta prática é write partitioned: cada conta tem uma região dona, onde acontecem todos os débitos dela.

Mas aí uma transferência entre uma conta de São Paulo e uma da Virgínia vira operação entre regiões, e voltam sagas, outbox e conciliação. Por isso muitos sistemas de pagamento escolhem ativo-passivo para o ledger, com R P O baixo por replicação síncrona, e aceitam R T O de minutos. Na entrevista: ativo-ativo funciona para leituras e dados sem invariantes entre registros. Para saldos, roteie cada conta para um único escritor, ou pague a latência do consenso.

> **Pausa:** Pergunta: por que last writer wins é perigoso para um ledger?

Porque um dos lançamentos concorrentes é sobrescrito em silêncio. O dinheiro saiu, mas o registro sumiu, e o ledger deixa de bater.


## Backup e restore

O Postgres tem backups lógicos, com P G dump, um retrato num momento. E físicos, com arquivamento do write-ahead log. Para o projeto, o lógico basta. Faça o dump, e restaure num banco novo, cronometrando. Esse tempo é o seu R T O medido.

Anote no documento: a frequência do backup é o seu R P O. O tempo de restore mais as verificações é o seu R T O. E o tamanho do dump.

Para um R P O menor, você usaria um backup base mais o arquivamento contínuo do wal. Aí dá para reaplicar o log até um segundo antes do delete errado. É o point-in-time recovery.

E um restore só está pronto depois de verificado. No mínimo, a contagem de linhas por tabela, e o invariante do ledger: os lançamentos de cada transferência somam zero. Essa consulta não pode retornar nenhuma linha.


## Expand and contract

Durante um rolling deploy, código antigo e novo rodam juntos, contra o mesmo banco. Renomear uma coluna numa única migração quebra a produção: no commit do rename, as queries de todos os pods antigos falham. A técnica é o parallel change, também chamado expand and contract, descrita por Danilo Sato. Veja o cenário de sexta.

Expand: acrescente a coluna nova, anulável, sem default, uma mudança rápida no catálogo. E um trigger que copia as escritas de uma coluna para a outra. Os clientes antigos continuam funcionando.

Backfill: copie as linhas antigas em lotes pequenos, de cinco mil, para evitar locks longos e transações enormes. Repita até zero linhas.

Migrar: implante o código que lê e escreve só a coluna nova, e acrescente as constraints.

Contract: depois que todos os pods antigos saíram, remova o trigger, e depois a coluna antiga.

Cada passo é um deploy próprio, e pode ser revertido sozinho. Nunca existe um momento em que o código em execução e o schema discordam. E agende o contract no dia do expand: pular essa fase deixa duas versões de tudo, pior que antes. No projeto, rode o k 6 durante a migração. Taxa de erro estável em todos os passos prova sem downtime.

> **Pausa:** Pergunta: por que não fazer o rename numa migração só?

Porque durante o rolling deploy há pods com o código antigo, que ainda usam o nome antigo. No commit do rename, as queries deles falham.


## Feature toggles

O parallel change separa schema de código. As feature toggles separam implantar código de liberar comportamento. A nova rota de banco parceiro pode ficar em produção uma semana, desligada, e ser ligada para um por cento quando você quiser. Pete Hodgson classifica as toggles.

Release: código inacabado em produção, desligado, por dias ou semanas. Como uma nova tela de extrato.

Experiment: testes A B, estáveis por usuário, pelo tempo de ter estatística.

Ops: controlar o comportamento operacional, alteradas rápido. Como desligar o PDF de extrato no pico de carga.

Permissioning: funcionalidades para usuários específicos, que podem durar anos. Como limites maiores para contas empresariais verificadas.

E toggles têm custo de manutenção: caminhos extras, testes extras, confusão. Mantenha o estoque pequeno: crie a tarefa de remoção junto com a toggle, e defina expiração. O incidente caríssimo da Knight Capital veio de código antigo esquecido atrás de uma flag. Numa carteira, uma toggle esquecida que roteia clientes para um parceiro desativado é um incidente de conciliação esperando para acontecer.


## Kill switch e canary

Um toggle router com rollout percentual estável: faça o hash da flag com o I D do usuário, e compare com o percentual. O mesmo usuário cai sempre do mesmo lado, e o toggle point fica num lugar só.

Duas ideias amarram o módulo. Kill switches: ops toggles de longa duração que funcionam como um circuit breaker operado à mão. Num incidente, um operador desliga uma funcionalidade não essencial para poupar capacidade. É o load shedding de terça, feito por uma pessoa.

E canary release: ligue para uma pequena coorte aleatória, um por cento, compare as métricas de negócio com o resto, e amplie só se os números forem bons. Diferente de liberar primeiro para usuários internos, que são um grupo escolhido, não uma amostra.

Incluir o nome da flag no hash dá a cada flag uma coorte independente. Senão o mesmo um por cento azarado receberia todas as novidades ao mesmo tempo. No projeto, ops toggles para o breaker e o rate limiter deixam a comparação de antes e depois limpa.

> **Pausa:** Pergunta: qual a diferença entre um canary release e liberar primeiro para os funcionários?

O canary é uma amostra aleatória de clientes reais, comparada com o resto. Funcionários são um grupo escolhido, que não representa o uso real.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: R P O e R T O, em uma frase cada.

R P O é quanto dado, medido em tempo, você aceita perder. R T O é quanto tempo você aceita ficar fora do ar.

> **Pausa:** Pergunta dois: quais são os passos do parallel change?

Expand, acrescentando a versão nova ao lado da antiga. Migrate, movendo os clientes. E contract, removendo a antiga quando ninguém mais usa.

> **Pausa:** Pergunta três: o que é um kill switch?

Uma ops toggle que desliga uma funcionalidade não essencial durante um incidente, como um circuit breaker manual.


## O que anotar e próximo passo

Anote com as suas palavras: R P O, R T O e as quatro estratégias. Por que ativo-ativo com saldos é difícil. O expand e contract da sua renomeação. E os tipos de toggle, com kill switch e canary.

Depois, no lab, escreva o script de backup, escolha o cenário de migração, e liste as tarefas de quinta e sexta. Até a próxima aula.
