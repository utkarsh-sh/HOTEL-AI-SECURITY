import cv2
import torch
import torchvision

from torchvision.models.detection import (
    ssdlite320_mobilenet_v3_large,
    SSDLite320_MobileNet_V3_Large_Weights,
)


class PersonDetector:
    """Detect people using a pretrained TorchVision detector."""

    def __init__(self, confidence_threshold: float = 0.50):
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        print(f"Using device: {self.device}")

        if self.device.type == "cuda":
            print(
                f"GPU: {torch.cuda.get_device_name(0)}"
            )

        self.weights = (
            SSDLite320_MobileNet_V3_Large_Weights.DEFAULT
        )

        self.model = ssdlite320_mobilenet_v3_large(
            weights=self.weights
        )

        self.model.to(self.device)
        self.model.eval()

        self.transforms = self.weights.transforms()

        # COCO class index for "person"
        self.person_class_id = 1

        self.confidence_threshold = confidence_threshold

    def detect(self, frame):
        """
        Detect people in a BGR OpenCV frame.

        Returns:
            List of dictionaries containing bounding box
            coordinates and confidence.
        """

        # OpenCV uses BGR.
        # TorchVision models expect RGB.
        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        # Convert HWC -> CHW
        image = torch.from_numpy(
            rgb_frame
        ).permute(2, 0, 1)

        # Apply model preprocessing
        image = self.transforms(image)

        image = image.to(self.device)

        with torch.inference_mode():
            prediction = self.model([image])[0]

        detections = []

        boxes = prediction["boxes"].detach().cpu()
        labels = prediction["labels"].detach().cpu()
        scores = prediction["scores"].detach().cpu()

        for box, label, score in zip(
            boxes,
            labels,
            scores
        ):
            confidence = float(score)

            if (
                int(label) == self.person_class_id
                and confidence >= self.confidence_threshold
            ):
                x1, y1, x2, y2 = box.tolist()

                detections.append(
                    {
                        "class": "person",
                        "confidence": confidence,
                        "box": [
                            int(x1),
                            int(y1),
                            int(x2),
                            int(y2),
                        ],
                    }
                )

        return detections