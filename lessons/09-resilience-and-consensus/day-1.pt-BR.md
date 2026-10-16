# Módulo 9, segunda-feira: timeouts, retries, circuit breakers e bulkheads

[Módulo 9](../../modules/09-resilience-and-consensus.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Sua carteira digital depende de parceiros que você não controla: um banco parceiro para transferências, um processador de cartão, um provedor de Pix, um fornecedor de KYC. Um dia o provedor principal começa a responder em 30 segundos em vez de 300 milissegundos. Nada está "fora do ar". Todos os health checks estão verdes. Mesmo assim, em poucos minutos, sua API inteira para de responder, inclusive endpoints que nunca chamam esse provedor, como a tela de saldo.

Esse é o cenário do teste de domínio deste módulo, e o lab de hoje o reproduz com k6 e Toxiproxy. As quatro ferramentas de hoje (timeouts, retries com backoff e jitter, circuit breakers e bulkheads) existem para que uma dependência lenta degrade uma funcionalidade, não a empresa inteira.

## 1. Como uma dependência lenta derruba tudo

*Fonte principal: Microsoft Azure Architecture Center, "Bulkhead pattern", seção "Context and problem".*

Toda requisição que espera uma chamada remota segura alguma coisa enquanto espera: um socket, uma vaga em um pool de conexões HTTP, uma conexão de banco se a transação ainda estiver aberta, memória para o objeto da requisição. O artigo da Azure descreve a cadeia: um serviço deixa de responder, os recursos do consumidor ficam ocupados, o pool de conexões se esgota, e logo as requisições para *outros* serviços também falham. Essa cadeia é uma **falha em cascata**.

Uma conta rápida mostra como isso acontece rápido. A lei de Little diz que o número médio de requisições em andamento é igual à taxa de chegada vezes o tempo médio que cada uma passa no sistema (L = λ × W). Suponha que seu endpoint de transferência receba 50 requisições por segundo:

| Latência do provedor | Requisições em andamento (50 req/s) |
| --- | --- |
| 300 ms | 15 |
| 3 s | 150 |
| 30 s | 1.500 |

Se cada transferência em andamento segura uma de 20 conexões do Postgres enquanto chama o banco parceiro, o pool se esgota quase na hora com 30 s. Agora o endpoint de saldo, que só precisa de uma query de 2 ms, também espera por uma conexão. Os clientes veem o app inteiro travar.

Duas regras de design saem daí, e o resto da aula se apoia nelas:

- **Nunca segure uma conexão ou transação de banco aberta enquanto chama um serviço remoto.** Grave a transferência como `PENDING`, faça commit, chame o parceiro e registre o resultado em uma nova transação.
- **Toda espera precisa ter fim, e todo recurso compartilhado precisa ter uma fronteira.** Timeouts dão o fim. Bulkheads dão a fronteira.

## 2. Timeouts: escolhendo o número

*Fonte principal: Marc Brooker, Amazon Builders' Library, "Timeouts, retries, and backoff with jitter", a parte sobre timeouts.*

A primeira regra de Brooker é simples: coloque timeout em toda chamada remota, inclusive chamadas entre processos na mesma máquina. A parte difícil é escolher o valor. Alto demais, e você segura recursos à toa. Baixo demais, e você falha requisições que teriam dado certo, o que dispara retries e mais carga.

O método que ele descreve para os serviços da Amazon:

1. Decida que taxa de **timeouts falsos** você aceita, por exemplo 0,1% das chamadas.
2. Olhe a distribuição de latência do serviço chamado e pegue o percentil correspondente, aqui o p99.9.
3. Use esse valor como ponto de partida e ajuste.

Ele lista casos que pedem ajuste. Clientes na internet precisam de folga extra para redes ruins. Quando o p99.9 está muito perto do p50, acrescente uma margem, porque uma pequena variação causaria muitos timeouts de uma vez. Ele também conta a história de um timeout de 20 ms que falhava requisições depois de cada deploy, porque também cobria o handshake TLS das conexões novas. A lição: saiba o que o seu timeout realmente inclui (DNS, conexão, TLS, requisição, corpo da resposta).

No Node.js, o `fetch` não tem timeout por padrão. Passe um signal:

```typescript
// p99.9 do banco parceiro medido em ~1,2 s, então 2 s dá margem.
const res = await fetch(`${PARTNER_URL}/transfers`, {
  method: 'POST',
  headers: { 'Idempotency-Key': transfer.id, 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
  signal: AbortSignal.timeout(2_000),
});
```

Mais duas regras ligam hoje aos módulos anteriores:

- **Timeouts precisam ser aninhados.** Se o app mobile desiste depois de 10 s, o orçamento total da sua API precisa ser menor, e cada chamada dentro dela menor ainda. Um worker que continua fazendo retry depois que o cliente foi embora faz trabalho desperdiçado (o artigo de load shedding de terça fala disso).
- **Um timeout significa "não sei".** Como no Módulo 1, uma transferência cuja chamada ao parceiro dá timeout vai para `UNKNOWN`, e um job de conciliação pergunta o status ao parceiro depois. Ela nunca vai direto para `FAILED`.

## 3. Retries são egoístas

*Fonte principal: Brooker, "Timeouts, retries, and backoff with jitter", as partes sobre retries e idempotência.*

Um retry esconde falhas transitórias: um pacote perdido, um servidor reiniciando, um lock breve. Mas Brooker aponta que retries são egoístas. Um cliente que faz retry pede ao servidor que gaste mais da sua capacidade com a requisição daquele cliente. Quando falhas são raras, tudo bem. Quando o servidor está falhando *porque* está sobrecarregado, retries acrescentam carga justamente quando ele menos aguenta, e atrasam a recuperação.

A amplificação piora com a profundidade. O exemplo de Brooker: uma pilha de cinco camadas em que cada camada faz três retries pode multiplicar a carga no banco de dados lá embaixo por 3^5 = 243. Em uma carteira digital, a cadeia pode ser app mobile → API gateway → serviço de transferências → adaptador de pagamentos → banco parceiro. Se cada um fizer retry por conta própria, um soluço curto do parceiro vira uma enxurrada.

As regras práticas do artigo:

- **Faça retry em uma camada só.** Normalmente a camada dona da operação e da sua idempotency key, por exemplo o adaptador de pagamentos.
- **Faça retry só do que pode dar certo depois.** Um 5xx ou um erro de conexão pode dar certo depois. Um 4xx (requisição inválida, saldo insuficiente no parceiro) vai falhar do mesmo jeito, então não repita sem mudar nada.
- **Faça retry só de operações idempotentes.** Um timeout não prova que o efeito colateral não aconteceu. Brooker cita o `RunInstances` do EC2, que aceita um token do cliente por esse motivo. Seu adaptador envia o ID da transferência como idempotency key (Módulo 2), então um retry não consegue mover dinheiro duas vezes.
- **Limite retries com um orçamento.** Em vez de um circuit breaker, Brooker descreve um **token bucket local para retries**: os retries passam livremente enquanto há tokens, depois ficam limitados a uma taxa fixa. Ele conta que o AWS SDK ganhou esse comportamento em 2016. Uma versão simples: só permita retries enquanto eles forem menos de 10% das requisições recentes.

O orçamento de retries (retry budget) é o item 1 do TCM de quinta. Ele limita o pior caso: se toda chamada falhar, a carga total é no máximo 1,1 vez o normal, não 3 nem 243 vezes.

## 4. Backoff e jitter

*Fonte principal: Brooker, "Timeouts, retries, and backoff with jitter", as partes sobre backoff e jitter.*

Fazer retry imediatamente bate de novo em um servidor com dificuldade antes que ele tenha tempo de se recuperar. O **backoff exponencial** espera mais depois de cada tentativa que falha (100 ms, 200 ms, 400 ms, ...). Como a espera cresce rápido, as implementações colocam um **teto**. Brooker observa que só o teto não basta: os clientes passam a fazer retry para sempre no ritmo do teto. A resposta usual da Amazon é também limitar o número de tentativas.

O backoff tem um segundo problema. Se mil requisições falharam no mesmo instante (o parceiro reiniciou), todas esperam os mesmos intervalos e voltam nos mesmos instantes, em ondas sincronizadas. O **jitter** acrescenta aleatoriedade a cada espera para que os retries se espalhem. O artigo indica um post separado da AWS para as variantes. Uma variante comum sorteia uma espera entre zero e o valor exponencial com teto:

```typescript
function backoffMs(attempt: number, baseMs = 100, capMs = 5_000): number {
  const exp = Math.min(capMs, baseMs * 2 ** attempt);
  return Math.random() * exp; // jitter: qualquer ponto em [0, exp)
}
```

Brooker estende o jitter para além dos retries. Qualquer timer compartilhado por muitos hosts cria picos: pense em um job de conciliação que todo worker inicia às 00:00, ou em um cache de extrato que todo pod atualiza na virada do minuto. Ele descreve a Amazon acrescentando jitter a esse tipo de trabalho agendado e preferindo um deslocamento fixo por host (por exemplo, derivado do nome do host) a um valor aleatório novo a cada execução, porque um padrão fixo é mais fácil de depurar.

## 5. Circuit breaker

*Fonte principal: Martin Fowler, "Circuit Breaker" (2014). Fowler atribui ao livro "Release It!", de Michael Nygard, a popularização do padrão.*

Timeouts limitam quanto cada chamada espera, mas com um provedor morto toda chamada ainda espera o timeout inteiro. Com timeout de 2 s e 50 requisições por segundo, você ainda tem 100 requisições presas a qualquer momento, e cada uma termina em erro. Um **circuit breaker** para de fazer chamadas que quase certamente vão falhar.

Fowler o descreve como um invólucro em volta da chamada protegida que conta falhas. Nas palavras dele, "Once the failures reach a certain threshold, the circuit breaker trips" (quando as falhas atingem um certo limite, o circuit breaker desarma), e as chamadas seguintes retornam erro na hora, sem chegar ao fornecedor. Depois de um tempo, o breaker deixa passar uma chamada de teste para ver se o fornecedor se recuperou.

| Estado | O que acontece com uma chamada | Passa para |
| --- | --- | --- |
| **Fechado (closed)** | Vai até o fornecedor; as falhas são contadas | Aberto, quando as falhas passam do limite |
| **Aberto (open)** | Falha na hora, o fornecedor não é chamado | Meio-aberto, depois do reset timeout |
| **Meio-aberto (half-open)** | Uma chamada de teste passa | Fechado se ela der certo, aberto de novo se falhar |

Detalhes do artigo de Fowler que importam na prática:

- O exemplo simples dele desarma depois de 5 falhas. Ele observa que um breaker mais realista pode desarmar por **taxa de erro** (por exemplo 50%), e pode usar limites diferentes para erros diferentes, como um limite maior para timeouts do que para falhas de conexão.
- **Nem todo erro é falha.** Um parceiro que responde "saldo insuficiente" ou "conta inválida" está dando um resultado de negócio normal, e isso não pode desarmar o breaker.
- **Decida o fallback.** O exemplo de fallback de Fowler é colocar uma autorização de cartão de crédito em fila para processar depois. Em uma carteira digital: aceite a transferência como `PENDING`, coloque-a em uma fila e diga ao cliente que está em processamento.
- **Torne-o visível.** Registre em log toda mudança de estado, exponha o estado para monitoramento e deixe os operadores desarmarem ou rearmarem um breaker manualmente.

O artigo de Brooker acrescenta uma ressalva: breakers introduzem um comportamento modal difícil de testar e podem atrasar a recuperação, e é por isso que a Amazon muitas vezes prefere token buckets de retry. Os dois não se excluem. No lab você vai usar o opossum, uma biblioteca de Node.js:

```typescript
import CircuitBreaker from 'opossum';

const breaker = new CircuitBreaker(callPartnerBank, {
  timeout: 2_000,               // uma chamada mais lenta que isso conta como falha
  errorThresholdPercentage: 50, // abre quando metade das chamadas recentes falha
  resetTimeout: 30_000,         // espera 30 s antes de um teste meio-aberto
});
breaker.fallback((transfer) => enqueueForLater(transfer)); // retorna PENDING
breaker.on('open', () => logger.warn('breaker do banco parceiro ABERTO'));

const result = await breaker.fire(transfer);
```

## 6. Bulkheads

*Fonte principal: Microsoft Azure Architecture Center, "Bulkhead pattern", seções "Solution" e "Problems and considerations".*

O nome vem dos navios. O artigo da Azure explica: "If the hull of a ship is compromised, only the damaged section fills with water, which prevents the ship from sinking." (Se o casco de um navio é danificado, só a seção atingida se enche de água, o que evita que o navio afunde.) Um bulkhead em software divide os recursos em pools para que uma falha em um pool não esgote os outros.

O artigo descreve dois tipos:

- **Particionar os recursos do consumidor.** Um serviço que chama várias dependências ganha um pool de conexões separado para cada uma. Se uma dependência trava, só o pool dela enche.
- **Particionar as instâncias do serviço.** Agrupe instâncias por consumidor ou prioridade, para que um cliente pesado não deixe os outros sem recursos.

Em uma carteira digital, exemplos são:

- Um agente HTTP com limite próprio de conexões para cada parceiro (banco parceiro, processador de cartão, KYC). Um fornecedor de KYC lento não bloqueia transferências.
- Um pool separado do Postgres (ou uma réplica de leitura separada) para relatórios do back-office, para que uma exportação pesada não tire conexões do caminho de pagamento.
- Filas de workers separadas por parceiro, para que o acúmulo em uma não atrase as outras (o artigo sobre filas de terça volta a isso).

Um bulkhead mínimo de concorrência em TypeScript:

```typescript
class Bulkhead {
  private inFlight = 0;
  constructor(private readonly max: number) {}

  async run<T>(fn: () => Promise<T>): Promise<T> {
    if (this.inFlight >= this.max) throw new BulkheadFullError(); // rejeita, não enfileira
    this.inFlight++;
    try { return await fn(); } finally { this.inFlight--; }
  }
}

const partnerBank = new Bulkhead(30);
const kycVendor = new Bulkhead(10);
```

As considerações do artigo: escolha as partições pelos requisitos técnicos e de negócio (bounded contexts são um bom guia), pese o isolamento contra custo e complexidade, monitore cada partição separadamente e combine bulkheads com retries, circuit breakers e throttling. Ele também lista quando o padrão pode não servir: quando um uso menos eficiente dos recursos é inaceitável, ou quando a complexidade extra não é necessária. Um bulkhead reserva capacidade que fica ociosa nos dias bons. Esse é o preço.

## 7. Juntando tudo: o provedor de 30 segundos

*Esta seção combina as três fontes acima.*

Aqui está o cenário do teste de domínio, camada por camada. O banco parceiro vai de 300 ms para 30 s.

| Proteção | O que acontece |
| --- | --- |
| Nenhuma | As requisições em andamento se acumulam (1.500 a 50 req/s). Os pools de conexão se esgotam. Todos os endpoints ficam lentos, o p99 vai até o timeout do cliente, a taxa de erro sobe em tudo. |
| Timeouts (2 s) | Cada transferência falha depois de 2 s e vai para `UNKNOWN`. As requisições em andamento caem para cerca de 100. Os outros endpoints se recuperam em grande parte, mas cada transferência ainda custa 2 s e um erro. |
| + Retries sem orçamento | Cada chamada que falha é tentada mais 3 vezes. A carga no parceiro e no seu pool se multiplica. As coisas pioram, não melhoram. |
| + Backoff, jitter e retry budget | Os retries se espalham e ficam limitados a cerca de 10% de carga extra. Soluços transitórios ficam escondidos; uma queda real não é amplificada. |
| + Circuit breaker | Depois que a taxa de erro passa de 50%, as chamadas falham rápido e caem no fallback de `PENDING` mais uma fila. A latência para o cliente cai para milissegundos. Os testes meio-abertos detectam a recuperação. |
| + Bulkhead | Mesmo antes de o breaker abrir, o banco parceiro pode usar no máximo 30 vagas simultâneas. Saldo, extrato e KYC mantêm seus próprios recursos. |

No lab de hoje você mede a primeira linha: p99, taxa de erro e conexões abertas sem nenhuma proteção. Amanhã você acrescenta timeouts e o breaker e mede de novo. Na quinta, o TCM acrescenta o retry budget, bulkheads por provedor e rate limiting, e na sexta você plota o antes e o depois.

## O que anotar hoje

1. Os três estados de um circuit breaker, o que o move entre eles e quais erros do parceiro não podem contar como falha.
2. O que um bulkhead isola na sua carteira digital: liste os pools que você criaria (por parceiro, back-office, workers) e seus tamanhos.
3. Como você escolhe um timeout (taxa de timeouts falsos e percentil), e por que os timeouts precisam ser aninhados do cliente para dentro.
4. O que é uma tempestade de retries (o exemplo 3^5 = 243), e como fazer retry em uma camada só, mais um retry budget, evita isso.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Por que uma dependência lenta pode derrubar endpoints que nunca a chamam?
- Como Brooker sugere escolher o valor de um timeout?
- Por que Brooker diz que retries são egoístas?
- Que problema o jitter resolve e o backoff sozinho não resolve?
- O que acontece em cada um dos três estados de um circuit breaker?
- Por que um "saldo insuficiente" vindo do parceiro não pode desarmar o breaker?
- Quanto custa um bulkhead em um dia bom?

## Referências

- **Fonte principal:** Martin Fowler, ["Circuit Breaker"](https://martinfowler.com/bliki/CircuitBreaker.html), martinfowler.com, 2014. Leia a entrada inteira, incluindo as partes sobre limites, fallbacks e monitoramento. Gratuito.
- **Fonte principal:** Microsoft Azure Architecture Center, ["Bulkhead pattern"](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead). Leia "Context and problem", "Solution", "Problems and considerations" e "When to use this pattern". Gratuito.
- **Fonte principal:** Marc Brooker, ["Timeouts, retries, and backoff with jitter"](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/), Amazon Builders' Library, 2019. Leia inteiro; é o texto mais importante do dia. Gratuito.
- Michael Nygard, "Release It! Design and Deploy Production-Ready Software", Pragmatic Bookshelf. O livro a que Fowler atribui a popularização do circuit breaker; ele também descreve bulkheads. Livro pago, opcional.
