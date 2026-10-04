{{ config(severity='warn') }}

-- Recurso sem coleta bem-sucedida dentro do limite de aviso da sua cadência.
select recurso_id, cadencia_corrente, ultimo_sucesso, atraso_horas, limite_aviso_horas
from {{ ref('monitor_fontes') }}
where ultimo_sucesso is null or atraso_horas > limite_aviso_horas
