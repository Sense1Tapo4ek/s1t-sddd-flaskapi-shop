from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Money:
    amount: float

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")

    def __str__(self) -> str:
        return f"{self.amount:.2f}"


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    value: str

    def __post_init__(self) -> None:
        cleaned = (
            self.value.replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )
        if not cleaned.startswith("+") or len(cleaned) < 10:
            raise ValueError(f"Invalid phone number: {self.value}")

    def __str__(self) -> str:
        return self.value
