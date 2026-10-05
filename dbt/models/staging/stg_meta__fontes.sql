-- Recursos do manifesto (fontes/*.yaml), regravados a cada execução em meta/fontes.
select
    recurso_id,
    cadencia_corrente
from {{ source('meta', 'fontes') }}
