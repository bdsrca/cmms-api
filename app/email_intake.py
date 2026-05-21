"""Email intake formatting helpers."""


def build_email_intake_text(*, from_email: str, to_email: str, subject: str, body: str) -> str:
    cleaned_from = from_email.strip()
    cleaned_to = to_email.strip()
    cleaned_subject = subject.strip()
    cleaned_body = body.strip()
    return "\n".join(
        [
            "Email intake",
            f"From: {cleaned_from}",
            f"To: {cleaned_to}",
            f"Subject: {cleaned_subject}",
            "",
            "Body:",
            cleaned_body,
        ]
    )
