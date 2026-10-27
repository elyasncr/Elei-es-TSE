"""DTOs da API — contrato publico, independente do formato interno (parquet)."""
from pydantic import BaseModel


class Candidato(BaseModel):
    nr: str
    nome: str
    apelido: str


class Pleito(BaseModel):
    ano: int
    turno: int
    esq: Candidato
    dir: Candidato
    pct_esq: float
    pct_dir: float
    validos: int
    comparecimento: int


class Meta(BaseModel):
    pleitos: list[Pleito]
    regioes: list[str]
    ufs: list[dict]


class Linha(BaseModel):
    """Uma unidade geografica em um pleito."""
    id: str
    nome: str
    uf: str | None = None
    regiao: str | None = None
    cd_ibge: str | None = None
    esq: int
    dir: int
    outros: int
    branco_nulo: int
    validos: int
    comparecimento: int
    pct_esq: float
    pct_dir: float


class LinhaSwing(BaseModel):
    """Variacao de apoio de um recorte entre dois pleitos."""
    id: str
    nome: str
    uf: str | None = None
    regiao: str | None = None
    cd_ibge: str | None = None
    pct_esq_de: float
    pct_esq_para: float
    swing_esq: float          # pontos percentuais ganhos pela esquerda
    pct_dir_de: float
    pct_dir_para: float
    swing_dir: float          # idem para o adversario
    validos_de: int
    validos_para: int
    votos_esq_de: int
    votos_esq_para: int
    delta_comparecimento: float
