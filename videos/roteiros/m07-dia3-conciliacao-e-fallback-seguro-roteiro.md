# Roteiro · M7 · Dia 3 · Conciliação e fallback seguro


## Abertura

Esta é a aula em vídeo do módulo sete, dia três: conciliação e fallback seguro.

Cada parte de um pagamento mantém seu registro. Seu ledger diz uma coisa, o arquivo do adquirente outra, o extrato do banco parceiro uma terceira. Quando discordam, alguém está perdendo dinheiro. A conciliação compara esses registros e transforma cada divergência num ticket antes que vire prejuízo. O teste de domínio pergunta: um pagamento aprovado não aparece no arquivo de liquidação do dia seguinte. O que acontece? Hoje você recebe a resposta completa.


## O que é conciliação

A conciliação compara duas visões do mesmo dinheiro. A Modern Treasury transforma cada uma num objeto.

O Expected Payment é o que você esperava receber ou enviar. Na carteira, é o ledger: toda captura, todo Pix de saída e todo estorno cria uma expectativa.

A Transaction é o que a instituição diz que aconteceu. Na carteira, a linha do C S V de liquidação. Conciliar é ligar cada transaction aos expected payments que ela paga.

Duas regras. Todas as condições precisam bater: match parcial não é match. E quando vários expected payments casam com uma transaction, nada é conciliado automaticamente. Vai para revisão manual. Um matcher que chuta às vezes chuta errado, e o erro se esconde num status de conciliado que ninguém olha. Um matcher que se recusa a chutar dá mais trabalho, mas nunca mente.


## Regras e cardinalidade

Uma regra de conciliação é uma lista de condições: campo, operador e valor. As regras são avaliadas em sequência. Coloque primeiro as específicas, que casam por um identificador único, e depois as amplas. E existem três cardinalidades.

Uma transaction para um esperado: uma linha de liquidação para um pagamento capturado.

Uma transaction para vários: o adquirente paga um valor único pelo dia inteiro. O exemplo da documentação: uma transaction de cem concilia com três esperados, de dez, vinte e setenta.

Várias para um: um pagamento liquidado em parcelas fica conciliado quando a soma das transactions bate com o valor dele.

Na sua carteira, a primeira regra é mesmo acquirer ref ou mesmo end to end I D. Uma regra de reserva, mesmo valor, mesmo dia, mesmo cliente, só vale se produzir exatamente um candidato.


## Tolerâncias

Valores e datas reais variam. Há três tipos de tolerância.

Faixa de valor: o esperado tem um limite inferior e um superior, e a transaction concilia se cair dentro.

Variação em matches agrupados: fixa, na menor unidade da moeda, ou percentual.

Janela de data: a data da transaction precisa cair entre os limites do esperado.

Mas tolerância é decisão de negócio, não técnica. Se o adquirente desconta dois e meio por cento, compare o líquido do arquivo com o bruto menos a taxa esperada, e deixe a tolerância só para arredondamento: um ou dois centavos.

Para datas, uma janela de um ou dois dias úteis em torno da data esperada pega feriados e arquivos atrasados, sem esconder um pagamento que nunca chegou.

Uma tolerância larga esconde erros reais.


## Tipos de divergência

O job de conciliação do projeto não tem interface, mas precisa do mesmo resultado: todo registro termina casado, ou num relatório de divergências com um tipo claro. São cinco tipos.

Faltando no arquivo: o ledger tem uma captura, e não há linha de liquidação. A captura nunca chegou ao adquirente, ou o arquivo está atrasado. Primeira ação: consultar o status.

Faltando no ledger: linha de liquidação sem lançamento. Sua captura deu timeout, o adquirente processou, e você marcou como falha. Consulte, e faça o lançamento que falta ou estorne.

Duplicado: duas linhas para uma referência. Retry sem idempotência, ou arquivo carregado duas vezes. Confira os I Ds dos arquivos, e se for real, estorne a cobrança extra.

Valor diferente além da tolerância: captura parcial, taxa errada, erro de moeda. Compare com a autorização e o contrato.

Data trocada: casado, mas fora da janela. Feriado, batch atrasado, bug de fuso. Sinalize, e escale se repetir.

> **Pausa:** Pergunta: uma linha de liquidação sem lançamento no seu ledger. Qual a causa mais provável?

Uma captura que deu timeout: o adquirente processou, mas você marcou como falha. Consulte o status e faça o lançamento que falta, ou estorne.


## No Postgres

No Postgres, carregue cada C S V numa tabela de staging, normalizada. Um full outer join encontra os dois tipos de faltando numa consulta só: sem referência no arquivo é faltando no arquivo, sem pagamento no ledger é faltando no ledger. Depois, valor e data.

Duplicados precisam de uma verificação separada antes do join, com group by e having count maior que um. Senão o join produz, em silêncio, duas linhas casadas.

Grave o relatório numa tabela, com o I D da execução, para ver como uma divergência evolui ao longo dos dias.

E nunca deixe o job alterar o ledger sozinho. Ele reporta, e uma ação separada e auditada corrige.


## Integridade no Airbnb

O Airbnb define integridade transacional como movimentação de dinheiro precisa e sem surpresas. Com vários gateways e dezenas de processadores, cada parte é um ponto onde uma transação pode ficar fora de sincronia. E a conciliação clássica não bastava: dava só uma visão geral, só olhava quando o dinheiro trocava de mãos, e casava por identificadores. O pipeline deles faz o contrário.

Compara toda transação, inclusive as que não movem dinheiro, como cancelamentos.

Compara todo atributo: valor, moeda, status, meio de pagamento e tempo.

Compara toda etapa: bancos internos contra o gateway contra os relatórios do processador.

E mede desde o dia zero de um gateway novo. Com isso, ajustaram timeouts, tratamento de erro e retries.

Duas ideias para a carteira. Compare status, não só valor: capturado no seu ledger e anulado no adquirente tem I D e valor iguais, e está errado. E um arquivo de liquidação faltando ou atrasado já é uma divergência, que deve acionar alguém.


## O fallback seguro

Agora a orquestração de provedores. Rotear, escolher um provedor por pagamento, é simples. Fallback, tentar outro provedor para o mesmo pagamento, é de onde vêm as cobranças duplicadas.

Você chama o adquirente A, com a chave k A.

A chamada dá timeout. Se você manda na hora para o B, e A tinha aprovado, o cliente paga duas vezes. Timeout significa não sei. A tentativa fica como desconhecida.

Então consulte o status em A, pela mesma chave, com backoff e depois do lease.

E decida com base em fatos.

Se A aprovou, termina em A.

Se A diz que falhou, crie uma tentativa nova em B, com chave nova.

Se continua desconhecido, siga esperando, ou cancele em A e confirme o cancelamento. Nunca tente B. Não encontrado logo depois de um timeout não é prova, porque a requisição pode estar em trânsito.

> **Pausa:** Pergunta: a chamada ao adquirente A deu timeout. Por que não mandar direto para o B?

Porque A pode ter aprovado. Timeout quer dizer não sei. Mandar para B pode cobrar o cliente nos dois provedores.


## O banco garante

As regras viram restrições. Um pagamento, várias tentativas, cada uma com sua chave. E um índice único parcial: no máximo uma tentativa pendente, desconhecida ou completa por pagamento.

Com ele, o próprio banco recusa a tentativa B enquanto A estiver desconhecida ou completa. Só uma tentativa que falhou de fato libera a vaga.

Se a aprovação de A chegar depois que você desistiu, por webhook ou consulta, sucesso atrasado continua sendo sucesso. Registre, e cancele ou estorne na hora. A conciliação pegaria isso como faltando no ledger.

Quando a taxa de erro de A sobe, abra o circuit breaker e roteie os pagamentos novos para B. Só os novos. Os que já foram para A ficam com A até se resolverem.

O critério do projeto é: o fallback nunca cobra nos dois provedores. O teste injeta um timeout em A depois que A registrou a cobrança, e verifica que B nunca foi chamado.


## Teste de domínio

Ensaie a resposta do teste de domínio, em dois minutos.

O pagamento é um lançamento no ledger, com uma data esperada de liquidação.

O job diário casa pela referência do adquirente, e reporta como faltando no arquivo.

A primeira ação é uma consulta de status ao adquirente, não uma correção automática.

Dependendo da resposta: você espera um arquivo atrasado, captura de novo, ou faz o lançamento inverso e avisa o cliente.

E um arquivo faltando, ou um número crescente desses casos, dispara um alerta.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: dois expected payments casam com a mesma transaction. O que o motor faz?

Não concilia automaticamente. Sinaliza para revisão manual.

> **Pausa:** Pergunta dois: por que detectar duplicados antes do full outer join?

Porque o join, sozinho, produz duas linhas casadas sem avisar.

> **Pausa:** Pergunta três: o que libera o pagamento para uma tentativa no adquirente B?

Só uma tentativa em A que falhou de fato, confirmada pelo provedor. Desconhecida ou completa bloqueia, pelo índice único parcial.


## O que anotar e próximo passo

Anote com as suas palavras: o que é conciliação e as regras. As tolerâncias que você vai usar. Os cinco tipos de divergência. A visão do Airbnb. E no papel, o diagrama de fallback, marcando onde a chave muda e qual restrição impede a cobrança dupla.

Depois, no lab, crie os C S Vs com divergências plantadas: um de cada tipo, o caso aprovado mas não liquidado, um timeout em A que cobrou, e o arquivo de resultados esperados. Até a próxima aula.
