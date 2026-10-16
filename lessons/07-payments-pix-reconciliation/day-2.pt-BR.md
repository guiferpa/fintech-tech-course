# Módulo 7, terça-feira: Pix, devoluções e o MED

[Módulo 7](../../modules/07-payments-pix-reconciliation.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

No Brasil, o Pix é o principal caminho de entrada e saída de dinheiro de uma carteira digital. Ele é muito diferente de um pagamento com cartão. Não há autorização que dure dias, nem etapa de captura, nem arquivo de liquidação chegando na manhã seguinte: o dinheiro se move em segundos, 24 horas por dia. Essa velocidade elimina alguns problemas e cria outros. Um Pix errado não pode ser "cancelado" antes da liquidação, porque a liquidação já aconteceu. Ele só pode ser devolvido, e a fraude é tratada por um mecanismo próprio, com prazos rígidos.

Entrevistadores de fintechs brasileiras esperam que você conheça o vocabulário: SPI, DICT, chave Pix, end_to_end_id, devolução e MED. Hoje você recebe cada termo, de onde ele vem e o que ele significa para as suas tabelas. O dia termina com o design do laboratório de hoje, a máquina de estados de pagamento.

## 1. O que é o Pix, segundo o regulamento

*Fonte principal: Resolução BCB nº 1 e o Regulamento do Pix anexo (versão em inglês), artigos 3, 33, 34 e 36.*

O Pix é o arranjo de pagamentos instantâneos criado e operado pelo Banco Central do Brasil (BCB). O regulamento define pagamento instantâneo como uma transferência eletrônica em que a ordem de pagamento e a disponibilidade dos recursos para o recebedor acontecem em tempo real, e cujo serviço "is available 24 (twenty-four) hours a day and every day of the year" (art. 3º, XI). Para você, essa frase é um requisito de arquitetura: sem janelas de manutenção, sem batch noturno que bloqueie pagamentos e com plantão às 3 da manhã de um domingo.

A liquidação depende de quem são as partes:

- **Entre participantes diferentes**, a liquidação acontece no **SPI** (art. 33). O regulamento define o SPI como uma infraestrutura centralizada de liquidação bruta em tempo real, que move recursos entre titulares de Conta PI no BCB (art. 3º, XIX). "Bruta" significa que cada pagamento liquida individualmente, sem compensação no fim do dia.
- **Entre dois clientes do mesmo participante**, a liquidação acontece nos sistemas do próprio participante (art. 34). Sua carteira pagando outro usuário da sua carteira é uma transferência no ledger, não uma mensagem ao SPI.

O artigo 36 define quando um Pix é considerado **autorizado**: o prestador do pagador, depois das verificações de segurança, encontra saldo suficiente na conta do pagador e bloqueia esse valor para iniciar a liquidação. Repare no paralelo com ontem. O bloqueio é um **hold**, igual a uma autorização de cartão, mas dura segundos em vez de dias. No seu ledger, um Pix de saída cria um hold, a confirmação do SPI o transforma em lançamento e uma rejeição o libera.

O artigo 38 lista casos em que o prestador do pagador deve rejeitar um Pix. Entre eles estão exceder o tempo máximo de autorização, uma suspeita razoável de fraude e problemas de autenticação. O artigo 35 diz que os prazos máximos das transações ficam em um documento separado, o Manual de Tempos do Pix. Ou seja, "o Pix é instantâneo" é um nível de serviço regulado, com prazos que seu sistema precisa cumprir.

## 2. Participantes e o DICT

*Fonte principal: Resolução BCB nº 1, art. 3º da Resolução, artigos 23 a 29 e 45 a 52 do Regulamento.*

**Quem participa.** A participação é obrigatória para instituições autorizadas pelo BCB com "more than half a million active customer accounts", contando contas de depósito, de poupança e de pagamento pré-pagas. Instituições menores e as que apenas iniciam pagamentos podem aderir voluntariamente. O Regulamento lista as modalidades no artigo 23: provedor de conta transacional, ente governamental, liquidante especial e iniciador.

Nem todo participante se conecta ao SPI diretamente. Um **participante responsável** (artigos 26 a 29) pode assumir outras instituições que dependem dele. O artigo 24 acrescenta que instituições de pagamento não autorizadas pelo BCB precisam de contrato com um participante responsável e de capital mínimo de R$1.000.000. Uma empresa de carteira digital jovem costuma viver nesse mundo indireto: oferece Pix aos usuários por meio de um banco parceiro que se conecta ao SPI. É por isso que o seu TCM tem um "banco parceiro", e não uma conexão direta com o SPI.

**O DICT.** O DICT é o diretório de chaves Pix operado pelo BCB. Uma **chave Pix** é uma informação vinculada a uma conta transacional. Os tipos permitidos são número de celular, e-mail, CPF, CNPJ e chave aleatória. Quando um usuário digita uma chave, o prestador do pagador consulta o DICT para encontrar a conta por trás dela, mostra o nome do recebedor e só então envia o pagamento.

Algumas regras do DICT têm consequências diretas de engenharia:

- Participantes diretos do SPI devem acessar o DICT diretamente; os demais acessam por meio de um participante direto (art. 48).
- Participantes com acesso direto devem manter sua base interna de chaves sincronizada com o DICT, e a verificação de sincronismo fica disponível 24 horas por dia.
- Participantes devem detectar e tratar consultas excessivas de chaves que não resultam em pagamento. Consultas de chave revelam nomes, então um scraper consultando milhares de chaves é um ataque. Os rate limiters dos problemas de DSA desta semana são a ferramenta para isso.
- Cadastro, exclusão, portabilidade e reivindicação de posse de chaves devem estar disponíveis aos usuários finais das 8h às 20h, horário de Brasília, todos os dias.

## 3. Os identificadores: end_to_end_id, txid e rtrId

*Fonte principal: Banco Central do Brasil, especificação da API Pix (bacen/pix-api, openapi.yaml, versão 2.10.0).*

Todo Pix carrega identificadores, e escolher o certo como chave principal da reconciliação é uma decisão de design.

| Identificador | Quem cria | O que a especificação diz |
| --- | --- | --- |
| `endToEndId` (end_to_end_id, e2eid) | O prestador do pagador | "Id fim a fim da transação": o EndToEndIdentification que transita nas mensagens pacs.002, pacs.004 e pacs.008. Exatamente 32 caracteres alfanuméricos. |
| `txid` | O recebedor | Um identificador da transação cujo objetivo declarado é permitir que o prestador do recebedor ofereça conciliação de pagamentos ao recebedor. De 26 a 35 caracteres alfanuméricos, único por CPF/CNPJ do recebedor no contexto de uma cobrança. |
| `rtrId` | O prestador que devolve os recursos | O ReturnIdentification que transita na pacs.004 de uma devolução. Também com 32 caracteres. |
| `id` da devolução | O sistema do recebedor | Um id gerado pelo cliente para representar unicamente uma devolução. |

Os códigos pacs são tipos de mensagem ISO 20022 usados pelo SPI: a pacs.008 carrega um pagamento, a pacs.002 um relatório de status e a pacs.004 uma devolução. Nos exemplos da especificação, os ids fim a fim começam com `E` e os ids de devolução com `D`.

O que isso significa para o seu schema:

- Guarde o `end_to_end_id` em todo lançamento de Pix, com constraint de unicidade. É o único id que todas as partes (seu banco parceiro, o SPI, o outro prestador) compartilham. Uma notificação duplicada do banco parceiro então falha no insert, em vez de creditar duas vezes.
- Quando sua carteira cobra alguém com um QR code, gere você mesmo o `txid` e guarde-o no pagamento esperado. Quando o crédito chegar, você casa pelo `txid` para saber qual cobrança foi paga.
- Uma devolução ganha sua própria linha, ligada ao `end_to_end_id` original, com seu próprio `rtrId`.

```sql
CREATE TABLE pix_transfers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  end_to_end_id   char(32) UNIQUE,          -- conhecido quando o prestador do pagador o cria
  txid            varchar(35),
  direction       text NOT NULL CHECK (direction IN ('IN','OUT')),
  amount_cents    bigint NOT NULL CHECK (amount_cents > 0),
  status          text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE pix_returns (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  original_e2e_id      char(32) NOT NULL REFERENCES pix_transfers(end_to_end_id),
  return_id            varchar(35) NOT NULL,
  rtr_id               char(32) UNIQUE,
  amount_cents         bigint NOT NULL CHECK (amount_cents > 0),
  status               text NOT NULL,
  UNIQUE (original_e2e_id, return_id)
);
```

## 4. Devoluções

*Fonte principal: Resolução BCB nº 1, artigos 40 a 41-A do Regulamento; especificação da API Pix, endpoint `/pix/{e2eid}/devolucao/{id}`.*

Um Pix não pode ser cancelado depois que liquida. A resposta do regulamento é a **devolução** (o texto em inglês chama de refund). O artigo 40 diz que recursos já disponíveis na conta do recebedor podem ser devolvidos, no todo ou em parte. Em regra, quem inicia a devolução é o recebedor. Várias devoluções parciais do mesmo Pix são permitidas, até o valor original. O artigo 41-A fixa um prazo geral: a maioria das devoluções "must be initiated within 90 (ninety) days" da transação original.

A especificação da API Pix mostra como uma devolução é solicitada e acompanhada:

- `PUT /pix/{e2eid}/devolucao/{id}` solicita a devolução do Pix identificado por `e2eid`, com um `id` escolhido pelo cliente. Usar PUT com id escolhido pelo cliente torna a requisição naturalmente idempotente: enviá-la duas vezes nomeia a mesma devolução.
- O status da devolução é um entre `EM_PROCESSAMENTO`, `DEVOLVIDO` e `NAO_REALIZADO`.
- O valor da devolução tem teto: para um Pix comum, não pode passar do valor do próprio Pix.

No ledger, uma devolução é um **novo lançamento na direção oposta**, ligado ao original. Nunca atualize o valor do lançamento original. Mantenha um total acumulado de valores devolvidos por `end_to_end_id` e garanta `sum(devoluções) <= original` na mesma transação que insere a devolução, com lock de linha na transferência original, para que duas devoluções parciais concorrentes não passem ambas pela verificação.

## 5. O Mecanismo Especial de Devolução (MED)

*Fonte principal: Banco Central do Brasil, "Guia de implementação dos procedimentos de devolução no Pix, com ênfase no Mecanismo Especial de Devolução", versão 4.3, seções 2, 4.2 e 4.3; Resolução BCB nº 1, artigos 39-B e 41-B.*

Devoluções comuns dependem da boa vontade do recebedor. Vítimas de fraude não podem contar com isso. O **MED** (Mecanismo Especial de Devolução) permite que os prestadores bloqueiem e devolvam recursos sem pedir autorização ao cliente recebedor a cada vez. O Regulamento (art. 41-B) cobre suspeita de fraude e falhas operacionais. O guia descreve vários casos, cada um com seus próprios prazos e códigos de mensagem.

O fluxo de fraude, que o guia chama de Recuperação de Valores, funciona mais ou menos assim:

1. A vítima reclama com o **PSP do pagador**, que abre uma recuperação de valores no DICT. O guia diz que ele não deve analisar o mérito antes de abrir, e a transação deve ter no máximo 80 dias.
2. O DICT envia **notificações de infração** ao PSP que recebeu o Pix original e aos PSPs das transferências seguintes, porque fraudadores movem o dinheiro rapidamente.
3. O **PSP do recebedor** bloqueia na hora o valor solicitado (ou todo o saldo, se for menor), avisa seu cliente e analisa o caso em até 7 dias corridos. Ele fecha a notificação como "agreed" ou "disagreed".
4. Se a fraude for confirmada, o PSP do pagador tem 72 horas para iniciar a devolução. O PSP do recebedor então debita seu cliente e envia uma pacs.004 com código de motivo FR01, o que, segundo o guia, deve acontecer em até 6 horas em 99% dos casos.

Separadamente, o artigo 39-B cria o **bloqueio cautelar**. O PSP do recebedor deve bloquear recursos recebidos quando suspeitar de fraude, e o bloqueio "must be effected simultaneously with the credit". Ele deve avisar o cliente imediatamente, e o bloqueio dura no máximo 72 horas. O artigo 39-B também diz que esse bloqueio só se aplica a contas de pessoas naturais. O Regulamento acrescenta que só pode ser aberta uma solicitação de devolução por Pix.

| Caso do MED (seção do guia) | Quem age | Prazo principal no guia |
| --- | --- | --- |
| Falha operacional do PSP do pagador (4.1) | O PSP do recebedor devolve | 48 horas a partir da solicitação |
| Fundada suspeita de fraude (4.2) | O PSP do recebedor bloqueia e analisa | 7 dias corridos para analisar; 6 horas para devolver após a confirmação |
| Bloqueio cautelar (4.3) | PSP do recebedor | Até 72 horas para analisar |
| Recursos de fraude sem notificação nem bloqueio (4.4) | PSP do recebedor | Até 90 dias da transação |

As lições de engenharia para uma carteira que recebe Pix:

- "Bloqueado" é uma categoria de saldo. Seu ledger do Módulo 6 já tem holds; um bloqueio do MED é um hold que o cliente não criou e não pode liberar.
- Os prazos são em horas. Construa um job que liste toda notificação de infração aberta com seu horário limite, e alerte bem antes dele.
- O débito de uma devolução do MED pode acontecer dias depois do crédito, quando o cliente talvez já tenha gastado o dinheiro. Decida de antemão o que acontece quando o saldo é menor que o valor pedido; a regra do guia é bloquear o saldo que existir.

## 6. Open Finance em alto nível

*Fonte principal: Open Finance Brasil, página inicial.*

O Open Finance é uma iniciativa do BCB para aumentar a concorrência e melhorar os produtos financeiros para os consumidores. O site o define de forma simples: "Open Finance significa sistema financeiro aberto." Com o consentimento do cliente, uma instituição autorizada pode ver dados mantidos por outra, como saldos, cartões, extratos e investimentos. O site também diz que o compartilhamento permite novas formas de fazer pagamentos, transferências e Pix. Três pontos do site valem guardar. O cliente escolhe o que compartilhar, com quem e por quanto tempo, e pode cancelar a qualquer momento. Não existe um sistema central guardando os dados. É gratuito para o consumidor.

Para este curso, o Open Finance importa de duas formas. Primeiro, o Regulamento define o **serviço de iniciação de transação de pagamento** como aquele em que um pagamento é "instructed by an institution that does not hold the account". Pelo Open Finance, outro aplicativo poderia iniciar um Pix a partir da carteira do seu usuário. Segundo, o consentimento é um objeto de primeira classe: ele tem escopo, validade e revogação, e todo acesso precisa ser conferido contra ele.

## 7. O laboratório de hoje: máquina de estados de pagamento com tabela de transições

*Fonte principal: o ciclo de vida do PaymentIntent da Stripe (segunda-feira) e os artigos 36 a 41 do Regulamento do Pix, aplicados à carteira.*

O laboratório é uma máquina de estados de pagamento com uma tabela de transições válidas e testes. Coloque as regras em dados, não em `if`s espalhados. Assim uma única tabela responde "este movimento é permitido?" tanto para cartão quanto para Pix.

```typescript
type PaymentState =
  | 'CREATED' | 'AUTHORIZED' | 'CAPTURED' | 'SETTLED'
  | 'DECLINED' | 'VOIDED' | 'UNKNOWN' | 'REFUNDED_PARTIAL' | 'REFUNDED';

const transitions: Record<PaymentState, PaymentState[]> = {
  CREATED:          ['AUTHORIZED', 'DECLINED', 'UNKNOWN'],
  UNKNOWN:          ['AUTHORIZED', 'DECLINED', 'CAPTURED'], // resolvido por consulta de status
  AUTHORIZED:       ['CAPTURED', 'VOIDED'],
  CAPTURED:         ['SETTLED', 'REFUNDED_PARTIAL', 'REFUNDED'],
  SETTLED:          ['REFUNDED_PARTIAL', 'REFUNDED'],
  REFUNDED_PARTIAL: ['REFUNDED_PARTIAL', 'REFUNDED'],
  DECLINED: [], VOIDED: [], REFUNDED: [],
};

export function assertTransition(from: PaymentState, to: PaymentState) {
  if (!transitions[from].includes(to)) {
    throw new Error(`Invalid transition ${from} -> ${to}`);
  }
}
```

No Pix, `AUTHORIZED` é o hold de poucos segundos, e a captura acontece com a confirmação do SPI. Uma devolução leva um pagamento capturado ou liquidado para `REFUNDED_PARTIAL` ou `REFUNDED`.

Aplique a mesma regra no Postgres, para que um bug em um serviço não consiga pulá-la. Guarde os pares permitidos em uma tabela e confira cada atualização contra ela com um `UPDATE` condicional:

```sql
UPDATE payments p
   SET status = $2, updated_at = now()
 WHERE p.id = $1
   AND EXISTS (SELECT 1 FROM payment_transitions t
                WHERE t.from_status = p.status AND t.to_status = $2)
RETURNING p.status;
```

Zero linhas retornadas significa que o movimento era inválido ou que outro worker mudou a linha antes. Testes a escrever: toda transição listada funciona; todo par não listado falha; estados terminais não têm saída; duas atualizações concorrentes a partir do mesmo estado terminam com exatamente um vencedor.

## O que anotar hoje

1. SPI, DICT, chave Pix, end_to_end_id, txid e devoluções: uma linha cada, com suas palavras, e a coluna da tabela que guarda cada identificador.
2. Participantes do Pix (limite de obrigatoriedade, modalidades, participante responsável) e a obrigação de disponibilidade 24/7. Escreva onde sua carteira se encaixa e que regras de design a obrigação 24/7 impõe.
3. O fluxo do MED para fraude: quem abre, quem bloqueia, quem analisa, quem devolve, e os prazos (80 dias, 7 dias, 72 horas, 6 horas). Acrescente o bloqueio cautelar (72 horas).
4. Open Finance em três frases: o que é, como funciona o consentimento e o que significa iniciação de pagamento.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Onde liquida um Pix entre dois clientes da mesma instituição? E entre instituições diferentes?
- Segundo o regulamento, quando um Pix é considerado autorizado?
- O que é o end_to_end_id, quem o cria e qual o tamanho dele?
- Qual é a diferença entre o end_to_end_id e o txid?
- Um Pix pode ser cancelado depois da liquidação? O que acontece no lugar, e em que prazo geral?
- No fluxo de fraude do MED, quanto tempo o PSP do recebedor tem para analisar, e quanto tempo pode durar um bloqueio cautelar?
- Por que o endpoint de consulta de chaves no DICT deve ter rate limit?

## Referências

- **Fonte principal:** Banco Central do Brasil, [Resolução BCB nº 1 com o Regulamento do Pix (versão em inglês)](https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Pix_Regulation/Resolution_BCB_1.pdf). Passe pelo art. 3º da Resolução (participação) e, no Regulamento, pelo art. 3º (definições), arts. 23 a 29 (participação), arts. 33 a 41-C (liquidação, autorização, devoluções, MED) e o Capítulo XIII (DICT). Gratuito.
- **Fonte principal:** Banco Central do Brasil, ["Guia de implementação dos procedimentos de devolução no Pix, com ênfase no Mecanismo Especial de Devolução"](https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Guia_MED.pdf). Leia as seções 2, 4.1, 4.2 e 4.3. Gratuito.
- Banco Central do Brasil, [página do Pix (regulamento e manuais)](https://www.bcb.gov.br/estabilidadefinanceira/pix). A página central que leva ao regulamento, aos manuais do SPI e do DICT e às estatísticas. Gratuito. Abra no navegador (ela precisa de JavaScript).
- Banco Central do Brasil, [especificação da API Pix (bacen/pix-api no GitHub)](https://github.com/bacen/pix-api). O arquivo OpenAPI define `endToEndId`, `txid`, `rtrId` e os endpoints de devolução usados nas seções 3 e 4. Gratuito.
- Open Finance Brasil, [página inicial](https://openfinancebrasil.org.br/). Leia as partes sobre o que é e sobre consentimento. Gratuito.
