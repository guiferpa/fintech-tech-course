# Módulo 8, quarta-feira: tokens, autorização, limites antifraude e KYC

[Módulo 8](../../modules/08-security-compliance-risk.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Todo pedido para mover dinheiro precisa responder a três perguntas antes de tocar o ledger. Quem está chamando? Quem chama pode agir sobre esta conta específica? E, mesmo que possa, esta transferência em particular deve passar agora? A primeira é autenticação (tokens OAuth e JWTs). A segunda é autorização por objeto, onde mora o BOLA. A terceira é risco: limites, velocity checks e os deveres de prevenção à lavagem de dinheiro que uma instituição de pagamento brasileira tem por regulação.

Erre nas duas primeiras e um atacante move o dinheiro dos outros. Erre na terceira e uma conta legítima vira laranja de dinheiro roubado, ou sua checagem antifraude cai e leva todas as transferências junto. O TCM de sexta-feira constrói o serviço de limites, então a aula de hoje termina com o design dele.

## 1. Segurança de OAuth 2.0 em 2025: RFC 9700

*Fonte principal: RFC 9700, "Best Current Practice for OAuth 2.0 Security", janeiro de 2025, seções 2 e 4.*

A RFC 9700 reúne uma década de ataques a implantações de OAuth e os transforma em regras. A seção 2 é um checklist, e a seção 4 explica cada ataque em detalhe. As regras que um time de carteira deveria saber de cor:

| Regra (seção) | O que diz | O ataque que impede |
| --- | --- | --- |
| Comparação exata da redirect URI (2.1) | Servidores de autorização "MUST utilize exact string matching" ao comparar redirect URIs, exceto a porta em URIs localhost de apps nativos | Comparação por padrão ou curinga deixa um atacante registrar uma URI que captura códigos (4.1) |
| PKCE (2.1.1) | Clientes públicos devem usar PKCE, servidores "MUST support PKCE", e S256 é o método recomendado | Injeção de authorization code (4.5) e downgrade de PKCE (4.8) |
| Sem implicit grant (2.1.2) | Clientes "SHOULD NOT use the implicit grant" e devem usar o fluxo de authorization code | Tokens vazando por URLs, histórico do navegador e headers Referer (4.2, 4.3) |
| Sem password grant (2.4) | O resource owner password credentials grant não deve ser usado | O cliente vê a senha do usuário, e o fluxo não combina com autenticação multifator |
| Tokens vinculados ao remetente (2.2) | Access tokens devem ser vinculados ao cliente com mTLS (RFC 8705) ou DPoP (RFC 9449) | Um token roubado é inútil sem a chave privada do cliente (4.10) |
| Proteção do refresh token (2.2.2) | "Refresh tokens for public clients MUST be sender-constrained or use refresh token rotation" | Um refresh token vazado continua funcionando por meses |
| Menor privilégio (2.3) | Tokens devem ter privilégios mínimos e ser restritos a uma audiência (servidores de recurso específicos) | Um token do serviço de extrato é reutilizado contra o serviço de transferências (4.9, 4.10) |
| Autenticação do cliente (2.5) | Prefira métodos assimétricos como mTLS ou `private_key_jwt` | Segredos de cliente compartilhados que vazam |

A RFC também atualiza o modelo de atacante (seção 3). Ela não supõe mais só um atacante de rede. Supõe atacantes que podem rodar o próprio servidor de autorização (ataques de mix-up, seção 4.4), ler respostas de autorização que vazam por logs ou histórico do navegador e obter access tokens que vazam de servidores de recurso. Esse modelo mais amplo é o motivo de tokens vinculados ao remetente importarem: em um mundo onde tokens vazam, um bearer token é um cheque ao portador.

Repare na ligação com a segunda-feira. O mTLS não serve só para tráfego entre serviços. A RFC 9700 o usa para vincular tokens a um certificado de cliente, e APIs de bancos parceiros no Brasil, como as do Open Finance, costumam combinar OAuth com mTLS exatamente por isso.

## 2. Armadilhas de JWT

*Fonte principal: OWASP, "JSON Web Token Cheat Sheet".*

A maioria das carteiras usa JWTs como access tokens. Um JWT é fácil de emitir e fácil de verificar mal. As principais armadilhas do cheat sheet, na ordem em que você as encontraria:

1. **`alg: none`.** Algumas bibliotecas já aceitaram tokens sem assinatura. A regra: garanta que `"alg":"none"` não seja aceito pelo seu parser.
2. **Confusão de algoritmo.** Um verificador que deixa o header do token escolher o algoritmo pode ser enganado a tratar sua chave pública RSA ou EC como segredo HMAC. Como a chave pública é pública, o atacante consegue forjar tokens. O cheat sheet diz para fixar no código os algoritmos aceitos e não misturar algoritmos de chave pública com algoritmos de MAC.
3. **Confiar em chaves indicadas no header.** Headers como `jku`, `x5u` ou `jwk` podem apontar para uma chave do atacante. Pegue as chaves do `jwks_uri` configurado do emissor, nunca do token.
4. **Confusão de emissor e audiência.** Sempre valide `iss` e `aud`. O cheat sheet avisa: "never verify against a union of keys from several issuers."
5. **Confusão de tipo de token.** Um token de redefinição de senha ou um ID token não pode ser aceito como access token. Defina e cheque um `typ` específico por finalidade.
6. **Sem revogação embutida.** Um JWT vale até o `exp`. Mantenha expirações curtas. Se precisar de revogação, use uma denylist indexada por `jti` e `iss`, não pela string crua do token, o que o cheat sheet diz não ser seguro porque codificações alternativas ainda verificam.
7. **As claims são legíveis.** O payload é codificado, não criptografado. Nunca coloque CPF, saldo ou dados de cartão nas claims.
8. **Segredos HMAC fracos.** "Do not use a password as MAC secret." O segredo precisa de pelo menos 160 bits de entropia vindos de um gerador seguro.

Em NestJS com a biblioteca `jsonwebtoken`, quase tudo isso é questão de passar as opções certas:

```ts
import { verify } from 'jsonwebtoken';

const claims = verify(token, getPublicKey(kid), {
  algorithms: ['ES256'],              // lista fixa, nunca tirada do header
  issuer: 'https://auth.wallet.example',
  audience: 'transfers-api',
}) as { sub: string; scope: string };
```

Repare no `kid` aqui. A mesma ideia de ID de chave da assinatura de webhooks de segunda-feira permite ao seu servidor de autenticação rotacionar as chaves de assinatura: publique a nova chave pública no JWKS, comece a assinar com ela e remova a antiga depois que passar o maior tempo de vida de um token.

## 3. BOLA: autorize cada objeto

*Fonte principal: OWASP, "API1:2023 Broken Object Level Authorization".*

A autenticação diz que quem chama é o cliente 42. Ela não diz se o cliente 42 pode ler a conta 9137. A OWASP classifica o BOLA como fácil de explorar, disseminado e fácil de detectar: o atacante só troca um ID no path, na query, no header ou no corpo e vê se a resposta muda. O impacto vai de vazamento de dados até tomada completa da conta.

Os exemplos da OWASP incluem a API de uma montadora que destravava qualquer veículo a partir do VIN e um serviço de documentos cuja mutation de exclusão aceitava qualquer ID de documento. Traduzindo para uma carteira:

- `GET /accounts/9137/statement`: o extrato de qualquer pessoa.
- `POST /transfers` com `source_account_id: 9137`: gastar da conta de outra pessoa.
- `DELETE /beneficiaries/555`: remover a chave Pix salva de outro cliente.

Dois esclarecimentos da página da OWASP valem ser memorizados. Primeiro, comparar o ID do usuário do JWT com um parâmetro de ID "covers only a small subset of cases". A posse real costuma ser indireta: uma transferência pertence a uma conta, que pertence a um cliente, ou a uma empresa onde o usuário tem um papel. Segundo, se o usuário não deveria nem alcançar o endpoint, o problema é autorização por função (API5), não BOLA.

As defesas da OWASP: um mecanismo de autorização baseado em políticas e hierarquia de usuários, usado em toda função que recebe um ID vindo do cliente; IDs aleatórios e imprevisíveis, como GUIDs; e testes do mecanismo de autorização que bloqueiam o deploy quando falham.

O padrão mais robusto em um serviço com Postgres é fazer a posse parte da query, para que uma checagem esquecida não devolva nada em vez de devolver dados de outra pessoa:

```ts
async getStatement(userId: string, accountId: string) {
  const { rows } = await this.db.query(
    `SELECT e.* FROM ledger_entries e
       JOIN accounts a ON a.id = e.account_id
      WHERE a.id = $1 AND a.owner_id = $2
      ORDER BY e.seq DESC LIMIT 50`,
    [accountId, userId],
  );
  if (rows.length === 0 && !(await this.accountOwnedBy(accountId, userId))) {
    throw new NotFoundException(); // 404, não 403: não confirme que a conta existe
  }
  return rows;
}
```

UUIDs aleatórios dificultam a adivinhação, mas não são autorização. IDs vazam por URLs, logs e prints compartilhados. A checagem precisa estar lá de qualquer jeito, e um teste que chama todos os endpoints com IDs de outro usuário deveria estar no CI.

## 4. Limites e velocity checks

*Fonte principal: documentação da Stripe, "Fraud prevention rules" e "Supported attributes" do Radar.*

Mesmo uma transferência autenticada e autorizada pode ser fraude: um celular roubado, um cliente vítima de engenharia social, uma conta usada como laranja. O Radar da Stripe é um bom modelo de como checagens de risco baseadas em regras funcionam na prática.

**Ações.** Regras do Radar podem pedir 3D Secure, permitir (allow), bloquear (block) ou mandar um pagamento para revisão (review). As regras usam a sintaxe `{action} if {attribute} {operator} {value}`, por exemplo `Request 3D Secure if :risk_level: != 'normal' and :amount_in_usd: > 25`.

**Ordem e precedência.** Regras de pedir 3DS são avaliadas antes das regras de review, block e allow. Regras de review vêm depois das de block. Regras de allow se sobrepõem a todas as outras, inclusive às regras padrão da Stripe, então a documentação recomenda usá-las o mínimo possível e acrescentar `and :risk_level: != 'highest'` a elas.

**Atributos de velocidade.** O Radar expõe contadores por janelas de tempo (hourly, daily, weekly, all time), como `card_count_for_ip_address_hourly`, `declined_charges_per_card_number_daily` ou `total_charges_per_email_weekly`. Eles capturam os sinais clássicos de fraude: muitos cartões de um IP, muitas recusas em um cartão, uma rajada súbita de um cliente.

**Operar regras com segurança.** Os conselhos da documentação se traduzem direto para uma carteira:

- Na dúvida, use review em vez de block, olhe os falsos positivos e depois decida.
- Teste uma regra contra o histórico antes de ativá-la. O Radar simula regras sobre os últimos 6 meses de cobranças.
- Faça o rollout aos poucos com alocação de tráfego. Em 0%, a regra roda em modo shadow e só informa o que teria feito.
- Mantenha uma trilha de auditoria das mudanças de regras e acompanhe as métricas de cada regra, porque os padrões de fraude mudam.

**O serviço de limites da carteira.** Na sexta-feira você constrói uma versão mais simples. Um bom conjunto inicial de regras:

| Checagem | Regra de exemplo | Ação |
| --- | --- | --- |
| Limite por transferência | valor > R$ 5.000 | Bloquear, ou exigir autenticação reforçada |
| Limite diário acumulado | soma de hoje + valor > R$ 10.000 | Bloquear |
| Limite noturno | das 20:00 às 06:00 e valor > R$ 1.000 | Bloquear (bancos brasileiros aplicam limite noturno ao Pix) |
| Velocidade | mais de 5 transferências em 10 minutos | Revisão |
| Favorecido novo | primeira transferência para esta chave e valor > R$ 500 | Reter para revisão |

Uma contagem de velocidade pode ser uma query simples sobre uma tabela indexada, o que basta na escala de uma carteira:

```sql
SELECT count(*) AS n, coalesce(sum(amount), 0) AS total
FROM transfers
WHERE source_account_id = $1
  AND created_at > now() - interval '10 minutes'
  AND status <> 'REJECTED';
```

**Timeout e fallback.** O serviço de limites é uma dependência no caminho do dinheiro, então a lição do Módulo 1 vale: um timeout significa "não sei". Decida de antemão o que acontece nesse caso, escreva e teste:

- **Fail closed** (rejeitar ou reter) para valores altos, em que o custo de deixar uma fraude passar é maior que o de uma transferência atrasada.
- **Fail open com um limite local conservador** para valores pequenos, para que uma queda do serviço de risco não pare todo Pix de R$ 20.
- Sempre registre que a decisão foi um fallback, para que a transferência possa ser checada de novo quando o serviço voltar.

```ts
const decision = await withTimeout(this.limits.check(req), 150).catch(() => null);
if (decision === null) {
  return req.amountCents <= FALLBACK_MAX_CENTS
    ? { action: 'ALLOW', reason: 'limits_timeout_fallback' }
    : { action: 'HOLD', reason: 'limits_timeout_fallback' };
}
```

O Módulo 9 acrescenta o circuit breaker em volta dessa chamada.

## 5. KYC e prevenção à lavagem de dinheiro: Circular BCB 3.978/2020

*Fonte principal: Banco Central do Brasil, Circular nº 3.978, de 23 de janeiro de 2020.*

Regras de velocidade protegem seus clientes de fraudadores. Regras de prevenção à lavagem de dinheiro protegem o sistema financeiro dos seus clientes. No Brasil, instituições autorizadas pelo Banco Central, incluindo instituições de pagamento, precisam seguir a Circular 3.978/2020 sobre prevenção à lavagem de dinheiro e ao financiamento do terrorismo (PLD/FT). Hoje você só precisa passar pela estrutura dela:

| Capítulo | Tema | O que significa para engenheiros |
| --- | --- | --- |
| II, III | Política de PLD/FT e governança | Uma política aprovada pelo conselho e um diretor responsável nomeado |
| IV | Avaliação interna de risco | Produtos, clientes e canais classificados por risco; revisão a cada dois anos |
| V | Conhecer o cliente (KYC) | Identificação, qualificação e classificação de risco de cada cliente |
| VI | Registro de operações | Toda operação registrada, com origem e destino dos recursos |
| VII | Monitoramento, seleção e análise | Operações suspeitas selecionadas em até 45 dias e analisadas em até mais 45, cada uma em um dossiê documentado |
| VIII | Comunicação ao Coaf | Casos suspeitos comunicados "até o dia útil seguinte ao da decisão de comunicação" |
| IX | Conhecer funcionários, parceiros e terceirizados | Diligência sobre a própria equipe e os parceiros |
| XI | Avaliação de efetividade | Um relatório anual de efetividade |
| XII | Disposições finais, incluindo guarda | Informações de clientes, registros de operações e dossiês guardados "pelo período mínimo de dez anos" |

Três pontos se ligam diretamente ao seu código:

- **KYC são três passos, não um.** Identificação (quem é, com dados verificados), qualificação (onde mora, capacidade financeira, mantidas atualizadas) e classificação (em qual categoria de risco a pessoa cai). A classe de risco de um cliente deveria mudar os limites dele.
- **Pessoas expostas politicamente (PEPs)** precisam de procedimentos reforçados, e a condição dura cinco anos depois que deixam o cargo. Isso é um campo no seu modelo de cliente com efeito no monitoramento.
- **Sem dar ciência.** O artigo 50 diz que as comunicações ao Coaf são feitas sem dar ciência aos envolvidos. Um cliente cuja transferência está retida para análise de PLD não deveria ver "comunicado ao Coaf" no app.

Essa também é a obrigação legal por trás da resposta de LGPD de terça-feira. A guarda por dez anos da Circular é exatamente o tipo de "obrigação legal ou regulatória" para a qual o artigo 16 da LGPD permite conservar dados.

## 6. Preparação do TCM: o cliente de webhook de teste e a lista de tarefas

*Fonte principal: as tarefas do TCM deste módulo. Nada de IA para código do TCM; hoje você só planeja.*

O critério de aprovação é concreto: rotacionar a chave de assinatura com um cliente de webhook ativo causa zero falhas de verificação. Você precisa de um cliente que prove isso. Planeje um pequeno serviço separado que:

- Busca suas chaves públicas de verificação no endpoint público e as guarda em cache com um TTL.
- Diante de um `kid` desconhecido, busca as chaves de novo uma vez antes de falhar, para pegar rápido uma chave recém-publicada.
- Verifica assinatura e timestamp em todo webhook e conta sucessos e falhas, expondo os contadores em um endpoint que seu teste consegue ler.
- Roda sob carga constante (por exemplo, uma transferência a cada 200 ms gerando webhooks) enquanto você rotaciona.

Depois escreva a lista de tarefas de quinta e sexta, mapeada para os seis itens do TCM:

1. Assinatura com `kid` e duas chaves ativas; o endpoint de chaves públicas.
2. Script de rotação: publicar a nova, trocar a assinatura, esperar a sobreposição, aposentar a antiga. Teste: o contador de falhas fica em zero.
3. Envelope encryption do CPF: data key por registro, chave mestra no Vault Transit ou no KMS do LocalStack.
4. Redação de logs para CPF, dados de cartão e tokens, com um teste que faz grep nos logs.
5. Serviço de limites e velocity check com timeout e a tabela de fallback da seção 4.
6. `docs/m08.md`: a tabela STRIDE de terça-feira, o inventário de chaves (qual chave, onde, quem pode usar, período de rotação) e a tabela de retenção da LGPD.

## O que anotar hoje

1. Os ataques a OAuth que a RFC 9700 descreve (manipulação de redirect URI, injeção de code, vazamento de token, mix-up, tokens roubados) e a defesa para cada um.
2. Armadilhas comuns de JWT e as opções de verificação que as evitam.
3. Autorização por recurso: por que a checagem do ID do usuário do JWT não basta, e seu padrão de query para posse.
4. Limites e velocity checks: a tabela de regras da sua carteira, ações e precedência das regras, e o fallback quando a checagem dá timeout.
5. Deveres de KYC e PLD: a estrutura da Circular 3.978, os três passos de KYC, o prazo do Coaf e a guarda por dez anos.
6. Lab: o design do cliente de webhook de teste e a lista de tarefas do TCM.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Por que a RFC 9700 exige comparação exata de strings para redirect URIs?
- O que o PKCE impede, e qual método a RFC 9700 recomenda?
- O que é um token vinculado ao remetente (sender-constrained), e quais dois mecanismos a RFC 9700 cita?
- Como funciona um ataque de confusão de algoritmo em JWT, e qual opção única o impede?
- Por que devolver 404 em vez de 403 quando um usuário pede uma conta que não é dele?
- No Stripe Radar, qual tipo de regra se sobrepõe a todos os outros, e o que é o modo shadow?
- O que seu fluxo de transferência deve fazer quando o serviço de limites dá timeout?

## Referências

- **Fonte principal:** IETF, [RFC 9700, "Best Current Practice for OAuth 2.0 Security"](https://www.rfc-editor.org/rfc/rfc9700), janeiro de 2025. Leia a seção 2 por inteiro e depois as seções 4.1, 4.5, 4.8 e 4.10. Gratuito.
- OWASP Cheat Sheet Series, ["JSON Web Token Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html). Leia a página inteira. Gratuito.
- OWASP, ["API1:2023 Broken Object Level Authorization"](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/). Leia a página inteira, incluindo os cenários de ataque. Gratuito.
- Documentação da Stripe, ["Fraud prevention rules"](https://docs.stripe.com/radar/rules). Leia "Built-in rules", "Create rules" e "Construct transaction rules". Gratuito.
- Documentação da Stripe, ["Supported attributes"](https://docs.stripe.com/radar/rules/supported-attributes). Passe pelos contadores de velocidade usados na seção 4. Gratuito.
- Banco Central do Brasil, [Circular nº 3.978/2020](https://normativos.bcb.gov.br/Lists/Normativos/Attachments/50905/Circ_3978_v3_P.pdf). Passe pela estrutura de capítulos e depois leia o capítulo V (KYC) e os artigos 48 a 50 e 67. Gratuito.
