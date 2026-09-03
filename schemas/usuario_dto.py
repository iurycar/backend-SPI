from dataclasses import dataclass

@dataclass
class LoginDTO:
    """
    Data Transfer Object (DTO) para representar os dados de login do usuário.
    Contém os campos necessários para autenticação do usuário.
    A classe fornece um método de classe `from_dict` para criar uma instância 
    a partir de um dicionário, garantindo que os campos obrigatórios estejam 
    presentes e válidos.
    """

    email: str
    password: str

    @classmethod
    def from_dict(cls, data: dict):
        """
        Cria uma instância de LoginDTO a partir de um dicionário.
        """
        
        if not isinstance(data, dict):
            raise ValueError("Payload invalid.")

        email = (data.get('email') or "").strip().lower()
        password = (data.get('password') or "").strip()

        if not email:
            raise ValueError("Email is required.")

        if not password:
            raise ValueError("Password is required.")

        return cls(email=email, password=password)


@dataclass
class SignupDTO:
    email: str
    password: str
    nome: str
    perfil: str
    sobrenome: str | None = None
    unidade: str | None = None
    telefone: str | None = None

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise ValueError("Payload invalid.")

        email = (data.get('email') or "").strip().lower()
        password = (data.get('password') or "").strip()
        nome = (data.get('nome') or "").strip()
        sobrenome = (data.get('sobrenome') or "").strip() or None
        perfil = (data.get('perfil') or "").strip()
        unidade = (data.get('unidade') or "").strip() or None
        telefone = (data.get('telefone') or "").strip() or None

        if not email:
            raise ValueError("Email is required.")

        if not password:
            raise ValueError("Password is required.")

        if not nome:
            raise ValueError("Nome is required.")

        if not perfil:
            raise ValueError("Perfil is required.")

        return cls(
            email=email,
            password=password,
            nome=nome,
            sobrenome=sobrenome,
            perfil=perfil,
            unidade=unidade,
            telefone=telefone
        )