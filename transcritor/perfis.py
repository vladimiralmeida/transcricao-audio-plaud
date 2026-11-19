"""Metadados dos perfis: nome de exibição e papéis sugeridos para os falantes."""

PERFIS = {
    "orientacao": {
        "nome": "Orientação",
        "descricao": "Sessões de orientação acadêmica",
        "papeis": ["Orientador(a)", "Orientando(a)", "Coorientador(a)", "Convidado(a)"],
        "documento": "Resumo da orientação",
    },
    "entrevista": {
        "nome": "Entrevista",
        "descricao": "Entrevistas de pesquisa (dado sensível)",
        "papeis": ["Entrevistador(a)", "Entrevistado(a)"],
        "documento": "Codificação temática preliminar",
    },
    "reuniao": {
        "nome": "Profissional",
        "descricao": "Reuniões de trabalho",
        "papeis": ["Coordenador(a)", "Participante", "Secretário(a)", "Convidado(a)"],
        "documento": "Ata",
    },
    "aula": {
        "nome": "Aula",
        "descricao": "Aulas e palestras",
        "papeis": ["Professor(a)", "Aluno(a)", "Monitor(a)", "Convidado(a)"],
        "documento": "Notas de estudo",
    },
}
