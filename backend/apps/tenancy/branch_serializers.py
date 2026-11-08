import re

from rest_framework import serializers

GSTIN_PATTERN = re.compile(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]")
# GST state/UT codes 01-38, plus 97 (other territory) and 99 (centre jurisdiction).
VALID_STATE_CODES = frozenset([f"{n:02d}" for n in range(1, 39)] + ["97", "99"])


class BranchGstIdentitySerializer(serializers.Serializer):
    """Validate a partial update of a branch's GSTIN and place-of-business state code."""

    gstin = serializers.CharField(required=False, allow_blank=True, max_length=15)
    state_code = serializers.CharField(required=False, allow_blank=True, max_length=2)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide gstin and/or state_code.")
        branch = self.instance
        gstin = attrs["gstin"].strip().upper() if "gstin" in attrs else branch.gstin
        state_code = attrs["state_code"].strip() if "state_code" in attrs else branch.state_code
        errors: dict[str, str] = {}
        if gstin and not GSTIN_PATTERN.fullmatch(gstin):
            errors["gstin"] = "Enter a GSTIN in the expected 15-character format."
        if "gstin" in attrs and "state_code" not in attrs and gstin and not errors:
            state_code = gstin[:2]
        if state_code and state_code not in VALID_STATE_CODES:
            errors["state_code"] = "Enter a valid two-digit GST state code."
        if gstin and state_code and not errors and gstin[:2] != state_code:
            errors["gstin"] = "The GSTIN's first two digits must match the state code."
        if errors:
            raise serializers.ValidationError(errors)
        return {"gstin": gstin, "state_code": state_code}
