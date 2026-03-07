from transformers import (
    Qwen3VLForConditionalGeneration,
    AutoProcessor,
    TextIteratorStreamer,
)
from transformers import BitsAndBytesConfig
import torch
import threading


class QuantConfigs:
    bit8 = BitsAndBytesConfig(
        load_in_8bit=True,
        bnb_8bit_compute_dtype=torch.float16,
        bnb_8bit_use_double_quant=True
    )
    bit6 = BitsAndBytesConfig(
        load_in_6bit=True,
        bnb_6bit_compute_dtype=torch.float16,
        bnb_6bit_use_double_quant=True
    )
    bit4 = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True
    )
    bit1 = BitsAndBytesConfig(
        load_in_1bit=True,
        bnb_1bit_compute_dtype=torch.float16,
        bnb_1bit_use_double_quant=True
    )
    config = {
        8: bit8,
        6: bit6,
        4: bit4,
        1: bit1
    }


class Agent:
    def __init__(self, model_path: str, quant: int | None = None, device_map: str = "auto") -> None:
        self.model_path = model_path
        self.quant_bits = quant
        self.device_map = device_map
        self.model = None
        self.processor = None

    def load(self) -> None:
        # quant_config = (
        #     QuantConfigs.config[self.quant_bits]
        #     if self.quant_bits is not None
        #     else None
        # )
        quant_config = BitsAndBytesConfig(
            load_in_1bit=True,
            bnb_1bit_compute_dtype=torch.float16,
            bnb_1bit_use_double_quant=True
        )

        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            self.model_path,
            quantization_config=quant_config,
            device_map=self.device_map,
            dtype=torch.float16,
            attn_implementation="flash_attention_2",
            trust_remote_code=True
        )
        self.processor = AutoProcessor.from_pretrained(self.model_path)
    
    def unload(self) -> None:
        del self.model
    
    def process(
        self,
        text: str,
        *,
        max_new_tokens: int = 256
    ) -> str:
        # Generate output
        inputs = self.processor(
            text=text,
            return_tensors="pt",
        ).to("cuda")

        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            tokenize=True,
            add_generation_prompt=False,
            return_dict=True,
        )

        output_ids = output_ids[:, inputs.input_ids.shape[1]:]

        return self.processor.decode(
            output_ids[0],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
    
    def stream(
        self,
        text: str,
        *,
        max_new_tokens: int = 256,
    ):
        inputs = self.processor(
            text=text,
            tokenize=True,
            add_generation_prompt=False,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device)

        streamer = TextIteratorStreamer(
            self.processor.tokenizer,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )

        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=max_new_tokens,
            use_cache=True,
        )

        thread = threading.Thread(
            target=self.model.generate,
            kwargs=generation_kwargs,
            daemon=True,
        )
        thread.start()

        for token in streamer:
            yield token
