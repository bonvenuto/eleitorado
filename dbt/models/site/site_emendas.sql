-- Pagamentos de emendas agregados para o site (autor, ano e favorecido), com o parlamentar quando o
-- autor está ligado a um. Só a fase de pagamento: empenho e liquidação repetiriam o valor.
select
    a.parlamentar_id,
    p.autor_codigo,
    max(a.autor_nome) as autor_nome,
    year(p.data_documento) as ano,
    p.favorecido_documento,
    max(p.favorecido_nome) as favorecido_nome,
    max(p.favorecido_cnpj_raiz) as favorecido_cnpj_raiz,
    sum(p.valor_pago) as pago
from {{ ref('fct_emenda_pagamento') }} as p
left join {{ ref('dim_autor_emenda') }} as a on a.autor_codigo = p.autor_codigo
where p.fase_despesa = 'Pagamento' and p.data_documento is not null
group by a.parlamentar_id, p.autor_codigo, year(p.data_documento), p.favorecido_documento
