import json
from pathlib import Path
from typing import Dict


class ProtocolFSReader:
    """
    Strict filesystem reader for MATERIALIZED protocol_validator artifacts.

    ARCHITECTURAL RULES:
    - No directory scanning
    - No discovery
    - No inference
    - Canonical filenames only
    - Missing or mismatched artifact == hard failure
    """

    def __init__(self, protocol_artifacts_root: Path):
        self.protocol_artifacts_root = protocol_artifacts_root

    # -------------------------------------------------
    # Internals (fail-loud by construction)
    # -------------------------------------------------

    @staticmethod
    def _artifact_path(directory: Path, code: str) -> Path:
        return directory / f"{code.lower()}.json"

    @staticmethod
    def _read_json(path: Path) -> Dict:
        if not path.exists():
            raise FileNotFoundError(f"Protocol artifact missing: {path}")

        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # -------------------------------------------------
    # Public API (NO DISCOVERY)
    # -------------------------------------------------

    def load_workflow(self, wf_code: str) -> Dict:
        path = self._artifact_path(
            self.protocol_artifacts_root / "workflows",
            wf_code,
        )
        data = self._read_json(path)

        if data.get("wf_code") != wf_code:
            raise RuntimeError(
                f"Workflow code mismatch in {path}: "
                f"expected '{wf_code}', found '{data.get('wf_code')}'"
            )

        return data

    def load_intent(self, in_code: str) -> Dict:
        path = self._artifact_path(
            self.protocol_artifacts_root / "intents",
            in_code,
        )
        data = self._read_json(path)

        # Support both in_code and intent_code field names
        artifact_code = data.get("in_code") or data.get("intent_code")
        if artifact_code != in_code:
            raise RuntimeError(
                f"Intent code mismatch in {path}: "
                f"expected '{in_code}', found '{artifact_code}'"
            )

        return data

    def load_all_intents(self) -> Dict[str, Dict]:
        intents_dir = self.protocol_artifacts_root / "intents"
        if not intents_dir.exists():
            raise FileNotFoundError(
                f"Protocol intents directory missing: {intents_dir}"
            )

        intents: Dict[str, Dict] = {}

        for path in intents_dir.glob("*.json"):
            data = self._read_json(path)
            # Support both in_code and intent_code field names
            in_code = data.get("in_code") or data.get("intent_code")
            if not isinstance(in_code, str):
                raise RuntimeError(
                    f"Intent missing 'in_code' or 'intent_code' in {path}"
                )

            expected = path.stem.upper()
            if in_code != expected:
                raise RuntimeError(
                    f"Intent code mismatch in {path}: "
                    f"expected '{expected}', found '{in_code}'"
                )

            intents[in_code] = data

        if not intents:
            raise RuntimeError("No intents found in protocol_validator/intents")

        return intents

    def load_all_transport_intents(self) -> Dict[str, Dict]:
        """Load all TI_ artifacts from ingress_intents directory."""
        ti_dir = self.protocol_artifacts_root / "ingress_intents"
        if not ti_dir.exists():
            return {}

        intents: Dict[str, Dict] = {}
        for path in ti_dir.glob("*.json"):
            data = self._read_json(path)
            ti_code = data.get("ti_code")
            if not isinstance(ti_code, str):
                continue

            expected = path.stem.upper()
            if ti_code != expected:
                raise RuntimeError(
                    f"TI code mismatch in {path}: "
                    f"expected '{expected}', found '{ti_code}'"
                )

            intents[ti_code] = data

        return intents

    def load_all_transport_egress(self) -> Dict[str, Dict]:
        """Load all TE_ artifacts from transport/egress directory."""
        te_dir = self.protocol_artifacts_root / "transport" / "egress"
        if not te_dir.exists():
            return {}

        egress: Dict[str, Dict] = {}
        for path in te_dir.glob("*.json"):
            data = self._read_json(path)
            te_code = data.get("te_code")
            if not isinstance(te_code, str):
                continue

            expected = path.stem.upper()
            if te_code != expected:
                raise RuntimeError(
                    f"TE code mismatch in {path}: "
                    f"expected '{expected}', found '{te_code}'"
                )

            egress[te_code] = data

        return egress

    def load_capability_contract(self, cc_code: str) -> Dict:
        path = self._artifact_path(
            self.protocol_artifacts_root / "capability_contracts",
            cc_code,
        )
        data = self._read_json(path)

        if data.get("cc_code") != cc_code:
            raise RuntimeError(
                f"Capability contract code mismatch in {path}: "
                f"expected '{cc_code}', found '{data.get('cc_code')}'"
            )

        return data

    def load_all_capability_contracts(self) -> Dict[str, Dict]:
        cc_dir = self.protocol_artifacts_root / "capability_contracts"
        if not cc_dir.exists():
            raise FileNotFoundError(
                f"Protocol capability_contracts directory missing: {cc_dir}"
            )

        contracts: Dict[str, Dict] = {}

        for path in cc_dir.glob("*.json"):
            data = self._read_json(path)
            cc_code = data.get("cc_code")
            if not isinstance(cc_code, str):
                raise RuntimeError(
                    f"Capability contract missing 'cc_code' in {path}"
                )

            expected = path.stem.upper()
            if cc_code != expected:
                raise RuntimeError(
                    f"Capability contract code mismatch in {path}: "
                    f"expected '{expected}', found '{cc_code}'"
                )

            contracts[cc_code] = data

        if not contracts:
            raise RuntimeError("No capability contracts found")

        return contracts

    def load_all_capability_transforms(self) -> Dict[str, Dict]:
        """Load all capability transform artifacts."""
        ct_dir = self.protocol_artifacts_root / "capability_transforms"
        if not ct_dir.exists():
            # CT directory optional - not all modules have CTs
            return {}

        transforms: Dict[str, Dict] = {}

        for path in ct_dir.glob("*.json"):
            data = self._read_json(path)
            ct_code = data.get("ct_code")
            if not isinstance(ct_code, str):
                raise RuntimeError(
                    f"Capability transform missing 'ct_code' in {path}"
                )

            expected = path.stem.upper()
            if ct_code != expected:
                raise RuntimeError(
                    f"Capability transform code mismatch in {path}: "
                    f"expected '{expected}', found '{ct_code}'"
                )

            transforms[ct_code] = data

        return transforms
