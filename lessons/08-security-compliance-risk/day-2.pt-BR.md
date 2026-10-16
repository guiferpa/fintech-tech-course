# Módulo 8, terça-feira: riscos de API, modelagem de ameaças, escopo PCI e LGPD

[Módulo 8](../../modules/08-security-compliance-risk.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

A segunda-feira foi sobre proteger bytes. Hoje o assunto é proteger o sistema e ficar do lado certo das regras. Três perguntas aparecem em quase toda entrevista e revisão de design em fintech:

- De que formas um atacante pode abusar da nossa API, e quais delas já cobrimos?
- Números de cartão chegam a tocar nossos servidores? Se sim, quanto da nossa infraestrutura passa a estar sob o PCI DSS?
- Um cliente pediu para excluirmos seus dados. O que excluímos, e o que a lei nos obriga a guardar?

Você responde a primeira hoje no lab, como um modelo de ameaças STRIDE. A segunda e a terceira são decisões de design caras de mudar depois, então você as toma cedo.

## 1. O OWASP API Security Top 10

*Fonte principal: OWASP API Security Top 10, edição 2023.*

A lista da OWASP é um vocabulário comum para riscos de API. A edição de 2023 tem dez itens. A tabela resume cada um em uma linha e dá um exemplo na carteira.

| ID | Risco | Na carteira, se parece com |
| --- | --- | --- |
| API1 | Broken Object Level Authorization (BOLA) | `GET /accounts/{id}/statement` devolve o extrato de qualquer conta para qualquer usuário logado |
| API2 | Broken Authentication | Tokens que nunca expiram, login fraco sem rate limit, um JWT aceito com `alg: none` |
| API3 | Broken Object Property Level Authorization | A resposta inclui `internal_risk_score`, ou um `PATCH` deixa o usuário definir `daily_limit` |
| API4 | Unrestricted Resource Consumption | Um atacante dispara milhares de códigos por SMS, que você paga por mensagem |
| API5 | Broken Function Level Authorization | Um usuário comum chama `POST /admin/accounts/{id}/unblock` e funciona |
| API6 | Unrestricted Access to Sensitive Business Flows | Bots criam milhares de contas para colher um bônus de cadastro |
| API7 | Server Side Request Forgery | Um campo de "URL de webhook" deixa o cliente fazer seu servidor chamar `http://169.254.169.254/` |
| API8 | Security Misconfiguration | Stack traces detalhados em produção, CORS permissivo, credenciais padrão |
| API9 | Improper Inventory Management | Um `/v1/transfers` antigo, sem a nova checagem de limites, ainda está no ar |
| API10 | Unsafe Consumption of APIs | Você confia no corpo do webhook do banco parceiro sem verificar a assinatura |

Três observações sobre a lista.

**O BOLA é o primeiro por um motivo.** A OWASP explica que APIs expõem endpoints que recebem IDs de objetos, e cada um deles é uma chance de esquecer a checagem de que quem chama pode mexer naquele objeto. Uma carteira está cheia desses endpoints: contas, transferências, extratos, cartões, favorecidos. A quarta-feira trata de BOLA a fundo.

**O API6 é sobre lógica de negócio, não sobre bugs.** A OWASP observa que esse risco não vem necessariamente de falhas de implementação. Seu endpoint de cadastro pode estar perfeitamente codificado e ainda assim ser abusado em escala. As defesas são limites, velocity checks e sinais de dispositivo, que é o tema de fraude de quarta-feira.

**O API7 importa se você envia webhooks.** O TCM deixa os clientes cadastrarem uma URL de webhook. Se o seu emissor segue qualquer URL que o cliente fornece, você construiu uma ferramenta de SSRF. Valide o esquema (só HTTPS), resolva o host e rejeite faixas de endereços privados e link-local, e não siga redirecionamentos cegamente.

## 2. Modelagem de ameaças com STRIDE

*Fonte principal: OWASP, "Threat Modeling Cheat Sheet". As categorias STRIDE foram criadas na Microsoft; o cheat sheet as apresenta com a propriedade de segurança que cada uma viola.*

O lab de hoje é um modelo de ameaças da sua carteira. O cheat sheet organiza a modelagem de ameaças em torno de quatro perguntas do Threat Modeling Manifesto: "What are we working on?", "What can go wrong?", "What are we going to do about it?" e "Did we do a good enough job?"

**No que estamos trabalhando: o diagrama de fluxo de dados.** O cheat sheet diz que um modelo deve mostrar entidades externas, processos, repositórios de dados e fluxos de dados, e deixar claras as fronteiras de confiança, já que elas "often represent possible attack points." Para a carteira, um primeiro diagrama tem:

- Entidades externas: o app do cliente, o banco parceiro, os clientes de webhook, a equipe de back-office.
- Processos: API gateway, serviço de transferências, serviço de ledger, emissor de webhooks, serviço de limites.
- Repositórios de dados: Postgres (ledger, clientes, dados pessoais), o message broker, o Vault.
- Fronteiras de confiança: internet para o gateway, gateway para os serviços internos, sua rede para o banco parceiro, sua rede para os endpoints de webhook dos clientes.

**O que pode dar errado: STRIDE.** Para cada elemento e cada fluxo que cruza uma fronteira, percorra seis categorias. O cheat sheet associa cada uma à propriedade que ela viola. Os exemplos na carteira e as mitigações abaixo são deste curso.

| Ameaça | Propriedade violada | Exemplo na carteira | Mitigação típica |
| --- | --- | --- | --- |
| **S**poofing | Autenticação | Um webhook falso de "pagamento recebido" de um falso banco parceiro | Verificar assinaturas do parceiro, mTLS com o parceiro |
| **T**ampering | Integridade | Alterar o valor de uma mensagem de transferência no broker | Mensagens assinadas ou autenticadas, ACLs de menor privilégio no broker |
| **R**epudiation | Responsabilização | Um funcionário estorna uma transferência e nega | Log de auditoria append-only com autor, horário e motivo |
| **I**nformation disclosure | Confidencialidade | CPFs e tokens aparecem nos logs da aplicação | Redação de logs, envelope encryption dos dados pessoais |
| **D**enial of service | Disponibilidade | Uma enxurrada de pedidos de transferência esgota o pool de conexões | Rate limits, timeouts, bulkheads (Módulo 9) |
| **E**levation of privilege | Autorização | Um usuário edita uma claim do JWT para `role: admin` | Verificar assinaturas com algoritmos fixos, papéis no servidor |

**O que vamos fazer a respeito.** O cheat sheet lista quatro respostas para cada ameaça: mitigar, eliminar, transferir ou aceitar. "Transferir" é bem real em pagamentos. Usar os campos de cartão hospedados por um processador transfere a ele a maior parte do risco com dados de cartão, que é a próxima seção.

Para o lab, escreva cada ameaça como uma linha: elemento, letra do STRIDE, cenário, resposta e um link para o código ou a tarefa que a implementa. Essa tabela é o primeiro rascunho de `docs/m08.md`.

## 3. PCI DSS em uma página

*Fonte principal: PCI Security Standards Council, biblioteca de documentos, "PCI DSS v4.0.1" e o "PCI DSS Quick Reference Guide". A página da biblioteca não listava o Quick Reference Guide quando esta aula foi escrita, então a lista de requisitos abaixo vem do artigo da Wikipedia sobre o PCI DSS, que cita os títulos dos requisitos da v4.0.1.*

O PCI DSS (Payment Card Industry Data Security Standard) se aplica a quem armazena, processa ou transmite dados de portador de cartão. Ele é definido pelo PCI Security Standards Council, fundado pelas bandeiras de cartão. A versão atual é a 4.0.1.

O padrão agrupa doze requisitos em seis objetivos:

| Objetivo | Requisitos |
| --- | --- |
| Construir e manter rede e sistemas seguros | 1. Controles de segurança de rede. 2. Configurações seguras. |
| Proteger os dados da conta | 3. Proteger os dados de conta armazenados. 4. Criptografia forte em trânsito por redes abertas. |
| Manter um programa de gestão de vulnerabilidades | 5. Proteger contra software malicioso. 6. Desenvolver e manter sistemas e software seguros. |
| Implementar medidas fortes de controle de acesso | 7. Restringir acesso pela necessidade de conhecer. 8. Identificar usuários e autenticar acessos. 9. Restringir acesso físico. |
| Monitorar e testar as redes regularmente | 10. Registrar e monitorar todo acesso. 11. Testar a segurança regularmente. |
| Manter uma política de segurança da informação | 12. Políticas e programas organizacionais. |

Dois termos decidem o quão doloroso é estar em conformidade:

- **Cardholder data environment (CDE)**: os sistemas que armazenam, processam ou transmitem dados de cartão, mais tudo o que se conecta a eles e poderia afetar sua segurança. Todo sistema no escopo precisa cumprir os requisitos.
- **Validação**: comerciantes menores preenchem um Self-Assessment Questionnaire (SAQ), enquanto os grandes são avaliados por um Qualified Security Assessor (QSA). Qual SAQ se aplica depende de como os dados de cartão passam por você.

Repare quanto da segunda-feira se encaixa diretamente nos requisitos 3 e 4: criptografia em repouso, gestão de chaves e criptografia forte em trânsito.

## 4. Tokenização: o melhor jeito de reduzir o escopo

*Fonte principal: documentação da Stripe, "Integration security guide". A ideia geral de tokenização é prática comum do setor.*

O controle PCI mais barato é nunca ver o número do cartão (o PAN). A **tokenização** troca o PAN por um token, um valor inútil fora do provedor que o emitiu. O provedor guarda o PAN no próprio cofre certificado PCI. Você guarda o token e cobra com ele.

O guia da Stripe mostra o que está em jogo. Se o seu negócio lida diretamente com dados de cartão, ele diz que "you might be required to meet more than 300 security controls in PCI DSS," além de hardware e software de segurança dedicados e auditores externos. As integrações de baixo risco, em vez disso, coletam os dados de cartão nos campos do provedor, e os dados vão direto para a Stripe sem passar pelos seus servidores. O guia também diz o que você pode manter: a bandeira, os quatro últimos dígitos e a data de validade não estão sujeitos ao PCI, então você pode guardá-los para mostrar "Visa •••• 4242".

Para a carteira, a regra é:

```text
Dispositivo do cliente ──dados do cartão──▶ campos hospedados / SDK do processador ──▶ cofre do processador
        │                                                                              │
        └────────────── token + últimos 4 + bandeira + validade ◀──────────────────────┘
                          │
                          ▼
                 sua API e o Postgres  (sem PAN, sem CVV, nunca)
```

Consequências para colocar nas suas notas de design:

- Seus servidores nunca recebem um PAN ou CVV, então nunca os registram em log. A redação de logs (item 4 de sexta-feira) é uma segunda linha de defesa, não a primeira.
- O token continua sensível. Quem tem a chave de API do processador e um token consegue cobrar o cartão. Guarde a chave de API no Vault e restrinja quem pode chamar o endpoint de cobrança.
- O escopo não some por completo. A página que hospeda os campos de cartão ainda importa, e é por isso que o guia da Stripe também trata de TLS, JavaScript de terceiros e Content Security Policy.

## 5. LGPD: excluir dados x guardar registros financeiros

*Fonte principal: Lei nº 13.709/2018 (LGPD), artigos 5, 7, 16 e 18. Esta é uma leitura de engenharia da lei, não aconselhamento jurídico. Confirme as decisões com o DPO e os advogados da sua empresa.*

A LGPD é a lei geral de proteção de dados do Brasil. O artigo 5 define dado pessoal como informação relacionada a pessoa natural identificada ou identificável, o que cobre CPF, nome, telefone, endereço e também o histórico de transações ligado a um cliente.

**Artigo 7: você precisa de uma base legal.** O tratamento só é permitido nas hipóteses listadas. O consentimento (I) é uma delas, e é a que as pessoas lembram, mas uma carteira se apoia principalmente em outras:

- II: cumprimento de obrigação legal ou regulatória pelo controlador.
- V: execução de contrato com o titular (o próprio contrato da conta).
- VI: exercício regular de direitos em processo judicial, administrativo ou arbitral (defender um chargeback ou uma ação).
- IX: interesses legítimos do controlador, exceto quando prevalecerem os direitos do titular.
- X: proteção do crédito.

**Artigo 18: os direitos do titular.** O cliente pode pedir confirmação de que você trata seus dados, acesso, correção, anonimização, bloqueio ou eliminação de dados desnecessários ou excessivos, portabilidade, informação sobre compartilhamento e revogação do consentimento. Leia o inciso VI com cuidado: o direito é à eliminação dos dados tratados **com o consentimento** do titular, "exceto nas hipóteses previstas no art. 16 desta Lei."

**Artigo 16: quando você pode guardar dados.** Dados pessoais devem ser eliminados quando o tratamento termina, mas a conservação é autorizada, entre outras finalidades, para "cumprimento de obrigação legal ou regulatória pelo controlador" (inciso I) e para uso exclusivo do controlador, desde que os dados sejam anonimizados (inciso IV).

Então um pedido de exclusão em uma carteira não significa `DELETE FROM customers`. Instituições financeiras têm deveres de guarda de registros. A leitura de quarta-feira, a Circular BCB 3.978/2020, exige que informações de clientes e registros de operações sejam guardados por pelo menos dez anos. O próprio ledger também é a fonte da verdade para saldos e conciliação, e o Módulo 6 o deixou append-only de propósito.

Um design que atende aos dois deveres:

| Dado | Em um pedido de exclusão |
| --- | --- |
| Preferências de marketing, tokens de push, perfis de analytics (baseados em consentimento) | Excluir agora |
| Dados tratados por contrato sem dever legal de guarda | Excluir quando a conta for encerrada e liquidada |
| Dados de KYC e registros de transações sob dever legal | Bloquear do uso normal, guardar até a data de retenção e então excluir |
| Lançamentos do ledger | Manter; eles referenciam `customer_id`, não o CPF nem o nome |

```sql
ALTER TABLE customer_pii
  ADD COLUMN blocked_at      timestamptz,
  ADD COLUMN retain_until    date;   -- definido pela base legal quando a conta é encerrada

-- Job diário: apaga dados pessoais cujo prazo de retenção passou
DELETE FROM customer_pii
WHERE blocked_at IS NOT NULL AND retain_until < current_date;
```

Dois hábitos de engenharia tornam isso viável. Primeiro, mantenha os dados pessoais em uma tabela própria, separada do ledger, para que bloqueá-los ou excluí-los nunca toque dados de dinheiro. Segundo, a DEK por registro de segunda-feira dá a você o **crypto-shredding**: destrua a data key de um cliente e toda cópia do CPF criptografado dele fica ilegível, inclusive cópias em backups que você não consegue editar. Anote a base legal de cada campo retido. "Guardamos por causa da lei X, até a data Y" é a resposta que um auditor e um cliente merecem.

## O que anotar hoje

1. Os dez riscos de API da OWASP em uma linha cada, com o BOLA em primeiro e um exemplo na carteira para pelo menos cinco deles.
2. O que o PCI DSS exige (seis objetivos, doze requisitos, o que é um CDE) e como a tokenização reduz o escopo, com o fluxo de dados desenhado.
3. Pedido de exclusão x dever de guardar registros financeiros: quais artigos da LGPD se aplicam (7, 16, 18) e a tabela da sua carteira de "excluir agora / bloquear e guardar / manter".
4. Lab: o diagrama de fluxo de dados com fronteiras de confiança e a lista de ameaças STRIDE como primeiro rascunho de `docs/m08.md`.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual é a diferença entre BOLA (API1) e Broken Function Level Authorization (API5)?
- Por que SSRF é um risco para um serviço que envia webhooks, e quais são duas defesas?
- Cite as seis categorias do STRIDE e a propriedade de segurança que cada uma viola.
- O que é um cardholder data environment, e por que a tokenização o torna menor?
- Quais dados do cartão uma carteira pode guardar sem entrar no escopo PCI, segundo o guia da Stripe?
- Pela LGPD, por que uma fintech pode se recusar a excluir o histórico de transações de um cliente após um pedido de exclusão?
- O que é crypto-shredding, e qual design de segunda-feira o torna possível?

## Referências

- **Fonte principal:** OWASP, ["OWASP API Security Top 10 (2023)"](https://owasp.org/API-Security/editions/2023/en/0x11-t10/). Leia a página de resumo e depois a página completa de API1, API4, API6 e API7. Gratuito.
- PCI Security Standards Council, [biblioteca de documentos](https://www.pcisecuritystandards.org/document_library/): "PCI DSS Quick Reference Guide" e "PCI DSS v4.0.1". Leia as partes sobre os doze requisitos e o escopo. Gratuito, com cadastro para alguns documentos.
- Lei nº 13.709/2018, [LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm). Leia os artigos 5, 7, 16 e 18. Gratuito.
- OWASP Cheat Sheet Series, ["Threat Modeling Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html). A fonte da seção 2 e o método do lab de hoje. Gratuito.
- Documentação da Stripe, ["Integration security guide"](https://docs.stripe.com/security/guide). A fonte da seção 4: integrações de baixo risco e quais dados de cartão você pode guardar. Gratuito.
- Wikipedia, ["Payment Card Industry Data Security Standard"](https://en.wikipedia.org/wiki/Payment_Card_Industry_Data_Security_Standard). Usada para a lista de objetivos e requisitos do PCI DSS v4.0.1. Gratuito.
