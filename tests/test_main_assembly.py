import unittest

from app import config
from app import main


class MainAssemblyTests(unittest.TestCase):
    def test_main_reuses_shared_prompt_and_contract_config(self) -> None:
        self.assertIs(main.DEFAULT_PROMPT_VERSIONS, config.DEFAULT_PROMPT_VERSIONS)
        self.assertIs(main.DEFAULT_CMMS_INTAKE_CONTRACT, config.DEFAULT_CMMS_INTAKE_CONTRACT)


if __name__ == "__main__":
    unittest.main()
