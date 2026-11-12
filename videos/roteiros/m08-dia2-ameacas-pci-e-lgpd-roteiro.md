# Roteiro · M8 · Dia 2 · Ameaças de API, PCI e LGPD


## Abertura

Esta é a aula em vídeo do módulo oito, dia dois: ameaças de API, P C I D S S e LGPD.

Ontem foi proteger bytes. Hoje é proteger o sistema e ficar do lado certo das regras. Três perguntas aparecem em quase toda entrevista de fintech. De que formas um atacante pode abusar da nossa API, e quais já cobrimos? Números de cartão tocam nossos servidores, e quanto da infraestrutura cai sob o P C I? E um cliente pediu para excluir seus dados: o que excluímos, e o que a lei obriga a guardar? A primeira você responde no lab, com um modelo de ameaças. As outras duas são decisões caras de mudar depois.


## OWASP API Top 10

A lista da O wasp é um vocabulário comum para riscos de API. São dez itens. Veja os que mais aparecem numa carteira.

API um, bola: autorização quebrada por objeto. Um endpoint de extrato que devolve o extrato de qualquer conta para qualquer usuário logado. É o primeiro por um motivo: toda API recebe I Ds de objetos, e cada um é uma chance de esquecer a checagem de dono. Uma carteira está cheia deles. Amanhã é o tema principal.

API dois, autenticação quebrada: tokens que nunca expiram, login sem rate limit, um J W T aceito com alg none.

API três, autorização por propriedade: a resposta inclui um score interno de risco, ou um patch deixa o usuário definir o próprio limite diário.

API cinco, autorização por função: um usuário comum chama o endpoint de admin que desbloqueia contas, e funciona.

API seis, fluxos de negócio sensíveis: bots criam milhares de contas para colher um bônus. Não é bug de implementação. O cadastro pode estar perfeito e ainda ser abusado em escala. A defesa são limites e sinais de dispositivo.

API sete, S S R F. Se o cliente cadastra uma URL de webhook e o seu emissor segue qualquer URL, você construiu uma ferramenta para atacar a sua própria rede interna.

Valide: só H T T P S, resolva o host e rejeite endereços privados e link local, e não siga redirecionamentos às cegas. Os outros itens são consumo de recursos sem limite, como disparar milhares de S M S pagos, configuração insegura, inventário de versões antigas no ar, e confiar em APIs de terceiros sem verificar.

> **Pausa:** Pergunta: o que é bola, e por que ele é o primeiro da lista?

Autorização quebrada por objeto: a API não confere se quem chama pode mexer naquele I D. É o primeiro porque toda rota com I D de objeto é uma chance de esquecer essa checagem.


## Modelagem STRIDE

O lab de hoje é um modelo de ameaças. O cheat sheet da O wasp organiza em quatro perguntas: no que estamos trabalhando, o que pode dar errado, o que vamos fazer, e fizemos o suficiente. A primeira é um diagrama de fluxo de dados: o app, o banco parceiro e os clientes de webhook de fora. Gateway, transferências, ledger e emissor de webhooks dentro. Postgres, broker e Vault como repositórios. E as fronteiras de confiança, que são os pontos de ataque. Para cada fluxo que cruza uma fronteira, percorra as seis letras do stride.

S, spoofing, viola autenticação: um webhook falso de pagamento recebido. Mitigue verificando a assinatura do parceiro, e com M T L S.

T, tampering, viola integridade: alterar o valor de uma transferência no broker. Mensagens autenticadas e permissões mínimas.

R, repudiation: um funcionário estorna uma transferência e nega. Um log de auditoria append-only, com autor, horário e motivo.

I, information disclosure: CPFs e tokens aparecem nos logs. Redação de logs e envelope encryption.

D, denial of service: uma enxurrada de pedidos esgota o pool de conexões. Rate limits, timeouts e bulkheads.

E, elevation of privilege: o usuário edita a claim do J W T para admin. Verifique a assinatura com algoritmo fixo, e decida o papel no servidor.

Para cada ameaça, há quatro respostas: mitigar, eliminar, transferir ou aceitar. Transferir é bem real em pagamentos: os campos de cartão do processador transferem a ele o risco dos dados de cartão. No lab, escreva cada ameaça numa linha: elemento, letra, cenário, resposta, e o link para o código. É o primeiro rascunho do documento do módulo.

> **Pausa:** Pergunta: a qual letra do stride pertence um funcionário que estorna uma transferência e depois nega, e qual a mitigação?

Repudiation. A mitigação é um log de auditoria append-only, com quem fez, quando e por quê.


## PCI DSS

O P C I D S S se aplica a quem armazena, processa ou transmite dados de cartão. Ele é definido pelo conselho fundado pelas bandeiras, e a versão atual é a quatro ponto zero ponto um. São doze requisitos em seis objetivos.

Rede e sistemas seguros: controles de rede e configurações seguras.

Proteger os dados da conta: os armazenados, e com criptografia forte em trânsito. É exatamente a aula de ontem.

Gestão de vulnerabilidades: proteção contra malware e software seguro.

Controle de acesso: pela necessidade de conhecer, autenticação de usuários, e acesso físico.

Monitorar e testar: registrar todo acesso, e testar regularmente.

E uma política de segurança da informação.

Dois termos decidem o quão doloroso é. O C D E, ambiente de dados do portador: os sistemas que tocam dados de cartão, mais tudo o que se conecta a eles. Todo sistema no escopo cumpre os requisitos. E a validação: comerciantes menores preenchem um questionário de autoavaliação, e os grandes são avaliados por um auditor qualificado.


## Tokenização

O controle P C I mais barato é nunca ver o número do cartão, o pan. A tokenização troca o pan por um token, inútil fora do provedor que o emitiu. Se você lida com dados de cartão diretamente, pode ter mais de trezentos controles para cumprir.

O cliente digita o cartão no dispositivo.

Mas nos campos hospedados do processador, ou no S D K dele. Os dados vão direto para lá.

O processador guarda o pan no cofre certificado.

E devolve um token, mais a bandeira, os quatro últimos dígitos e a validade, que não estão sujeitos ao P C I. Você guarda isso para mostrar Visa final quatro dois quatro dois, e cobra com o token.

Consequências. Seus servidores nunca recebem pan ou C V V, então nunca os registram em log. A redação de logs é a segunda linha de defesa, não a primeira.

O token continua sensível: quem tem a chave de API do processador e um token consegue cobrar o cartão. A chave fica no Vault, e o endpoint de cobrança é restrito.

E o escopo não some por completo. A página que hospeda os campos ainda importa: T L S, JavaScript de terceiros e Content Security Policy.

> **Pausa:** Pergunta: quais dados do cartão você pode guardar sem cair no escopo do P C I?

O token, a bandeira, os quatro últimos dígitos e a validade. Nunca o pan completo nem o C V V.


## LGPD

Agora a LGPD. Esta é uma leitura de engenharia, não aconselhamento jurídico: confirme com o D P O e os advogados.

O artigo cinco define dado pessoal como informação de pessoa identificada ou identificável. Cobre CPF, nome, telefone, e também o histórico de transações ligado a um cliente.

O artigo sete exige uma base legal. Consentimento é a que todos lembram, mas uma carteira se apoia mais em outras: obrigação legal ou regulatória, execução do contrato da conta, defesa em processos, como um chargeback, interesse legítimo e proteção do crédito.

O artigo dezoito lista os direitos do titular: acesso, correção, portabilidade, eliminação. Mas leia com cuidado: o direito é à eliminação dos dados tratados com consentimento, exceto nas hipóteses do artigo dezesseis.

E o artigo dezesseis autoriza guardar dados para cumprir obrigação legal ou regulatória, ou anonimizados para uso exclusivo do controlador.

E instituições financeiras têm dever de guarda: a Circular do Banco Central três mil novecentos e setenta e oito exige guardar dados de clientes e registros de operações por pelo menos dez anos. Então um pedido de exclusão não é um delete from customers.


## Pedido de exclusão

Um design que atende aos dois deveres.

Preferências de marketing, tokens de push e perfis de analytics, baseados em consentimento: exclua agora.

Dados tratados por contrato, sem dever legal de guarda: exclua quando a conta for encerrada e liquidada.

Dados de K Y C e registros de transações, sob dever legal: bloqueie do uso normal, guarde até a data de retenção, e então exclua, com um job diário que apaga o que passou do prazo.

E os lançamentos do ledger ficam. Eles referenciam o customer I D, não o CPF nem o nome. Por isso os dados pessoais moram numa tabela separada do ledger: bloquear ou excluir nunca toca dados de dinheiro.

E a D E K por registro de ontem dá o crypto-shredding: destrua a data key de um cliente, e toda cópia do CPF criptografado fica ilegível, até em backups que você não consegue editar. Anote a base legal de cada campo retido. Guardamos por causa da lei X, até a data Y, é a resposta que um auditor e um cliente merecem.

> **Pausa:** Pergunta: um cliente pede exclusão. Por que você não pode simplesmente apagar as transações dele?

Porque há dever legal de guardar registros de operações por pelo menos dez anos, e o artigo dezesseis autoriza essa conservação. Você bloqueia, guarda até a data, e então exclui.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: deixar o cliente cadastrar qualquer URL de webhook expõe a qual risco?

S S R F, o API sete. O seu servidor pode ser usado para chamar endereços internos. Valide H T T P S, o host, e rejeite faixas privadas.

> **Pausa:** Pergunta dois: como a tokenização reduz o escopo do P C I?

Os dados do cartão vão direto do dispositivo para o processador. Seus servidores nunca veem o pan, só o token.

> **Pausa:** Pergunta três: o direito de eliminação da LGPD é absoluto?

Não. Ele cobre os dados tratados com consentimento, e o artigo dezesseis permite guardar o que a lei ou o regulador exige.


## O que anotar e próximo passo

Anote com as suas palavras: os riscos da O wasp com exemplos na carteira. O P C I e o fluxo de tokenização. E a sua tabela de exclusão, com os artigos da LGPD.

Depois, no lab, desenhe o fluxo de dados com as fronteiras de confiança e escreva a lista de ameaças do stride. Até a próxima aula.
