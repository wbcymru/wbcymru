"""Model III: Image-Based Reconditioning Estimator (C_recon).

Fine-tuned ResNet-50 with two classification heads reading listing photos
(listing.condition.photo_urls). Outputs feed logistics_friction.repair as
line_items with assessment_source = "vision_ai" — this model proposes
repair line items, it does not compute cost estimates directly; cost
lookup happens in REPAIR_COST_MATRIX below, keyed off predicted class.
"""

import torch
import torch.nn as nn
import torchvision.models as models

# Ordinal, worst-last: index also used as severity rank for cost lookup.
WEAR_CLASSES = ["excellent", "good", "fair", "replacement_required"]
COSMETIC_CLASSES = ["minor_touchup", "panel_replacement", "full_repaint"]


class EquipmentConditionCNN(nn.Module):
    """Dual-head classifier: mechanical wear + cosmetic condition.

    Training data: ~25,000 labeled undercarriage/track/sprocket images for
    compact track loaders, ~15,000 labeled rust/dent/weathering images for
    ag tractors. Both heads share the ResNet-50 backbone; only the two
    small FC heads are trained per-category, so a new equipment vertical
    needs new labeled images and a head fine-tune, not a new backbone.
    """

    def __init__(self, num_classes_wear=len(WEAR_CLASSES), num_classes_cosmetic=len(COSMETIC_CLASSES)):
        super().__init__()
        self.backbone = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        num_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Identity()

        self.fc_wear = nn.Sequential(
            nn.Linear(num_features, 256),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(256, num_classes_wear),
        )
        self.fc_cosmetic = nn.Sequential(
            nn.Linear(num_features, 256),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(256, num_classes_cosmetic),
        )

    def forward(self, x: torch.Tensor):
        features = self.backbone(x)
        return self.fc_wear(features), self.fc_cosmetic(features)


# Maps a predicted class to a repair line item appended to
# logistics_friction.repair.line_items. Amounts are placeholders pending a
# real parts/labor pricing feed per category — see logistics_friction.schema.json.
REPAIR_COST_MATRIX = {
    ("wear", "replacement_required"): {"issue": "undercarriage_wear", "estimated_cost": 2400, "required_for_sale": True},
    ("wear", "fair"): {"issue": "undercarriage_wear", "estimated_cost": 600, "required_for_sale": False},
    ("cosmetic", "full_repaint"): {"issue": "cosmetic_decay", "estimated_cost": 1800, "required_for_sale": False},
    ("cosmetic", "panel_replacement"): {"issue": "cosmetic_decay", "estimated_cost": 900, "required_for_sale": False},
}


def line_items_for_prediction(wear_class: str, cosmetic_class: str, confidence: float) -> list[dict]:
    """Translate predicted classes into logistics_friction.repair.line_items entries."""
    items = []
    for key in (("wear", wear_class), ("cosmetic", cosmetic_class)):
        line = REPAIR_COST_MATRIX.get(key)
        if line:
            items.append({**line, "confidence": confidence})
    return items
