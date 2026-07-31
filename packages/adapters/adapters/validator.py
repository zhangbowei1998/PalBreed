"""Data validator — validates canonical Pal data against schema constraints."""

from dataclasses import dataclass, field

from pl_agent.core.schema import Element, Pal


@dataclass
class ValidationResult:
    """校验结果."""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def is_clean(self) -> bool:
        return len(self.errors) == 0 and len(self.warnings) == 0


ELEMENT_VALUES = {e.value for e in Element}


class DataValidator:
    """对 canonical Pal 列表进行数据质量校验 (参见 DATA_LAYER_REQUIREMENTS.md §5)."""

    def validate(self, pals: list[Pal]) -> ValidationResult:
        result = ValidationResult()

        self._check_uniqueness(pals, result)
        for pal in pals:
            self._check_required(pal, result)
            self._check_ranges(pal, result)
        self._check_distribution(pals, result)

        return result

    def _check_uniqueness(self, pals: list[Pal], r: ValidationResult):
        # V1: number unique
        numbers = [p.number for p in pals]
        if len(numbers) != len(set(numbers)):
            r.errors.append("V1: duplicate `number` values found")
        # V2: id unique
        ids = [p.id for p in pals]
        if len(ids) != len(set(ids)):
            r.errors.append("V2: duplicate `id` values found")

    def _check_required(self, pal: Pal, r: ValidationResult):
        # V3: combi_rank > 0
        if pal.combi_rank <= 0:
            r.errors.append(f"V3: {pal.id} combi_rank={pal.combi_rank} <= 0")
        # V4: cn_name non-empty
        if not pal.cn_name:
            r.errors.append(f"V4: {pal.id} cn_name is empty")
        # V5: elements non-empty and valid
        if not pal.elements:
            r.errors.append(f"V5: {pal.id} has no elements")
        else:
            invalid = [e for e in pal.elements if (
                e.value if hasattr(e, 'value') else e
            ) not in ELEMENT_VALUES]
            if invalid:
                r.errors.append(f"V5: {pal.id} invalid elements: {invalid}")

    def _check_ranges(self, pal: Pal, r: ValidationResult):
        # V6: rarity 1-10
        if not (1 <= pal.rarity <= 10):
            r.warnings.append(
                f"V6: {pal.id} rarity={pal.rarity} outside 1-10"
            )
        # V7: work_suitability — warn if any level > 10 (no hard cap)
        ws = pal.work_suitability
        for field_name in ws.__dataclass_fields__:
            level = getattr(ws, field_name, 0)
            if level > 10:
                r.warnings.append(
                    f"V7: {pal.id}.{field_name}={level}, exceeds expected max 10"
                )

    def _check_distribution(self, pals: list[Pal], r: ValidationResult):
        # V8: wild_count ratio
        wild_count = sum(1 for p in pals if p.is_wild)
        if wild_count < len(pals) * 0.5:
            r.warnings.append(
                f"V8: wild pals {wild_count}/{len(pals)} < 50%"
            )
        # V10: combi rank jump between adjacent numbers
        sorted_by_num = sorted(pals, key=lambda p: p.number)
        for i in range(1, len(sorted_by_num)):
            prev, curr = sorted_by_num[i - 1], sorted_by_num[i]
            if abs(curr.combi_rank - prev.combi_rank) > 500:
                r.info.append(
                    f"V10: combi_rank jump {prev.combi_rank}->{curr.combi_rank}"
                    f" between #{prev.number} {prev.cn_name} and #{curr.number} {curr.cn_name}"
                )
