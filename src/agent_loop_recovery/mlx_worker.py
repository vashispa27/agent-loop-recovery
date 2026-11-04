"""Optional MLX environment entry point, isolated from graph dependencies."""

import sys

if __name__ == "__main__":
    from mlx_lm import generate, load

    model, tokenizer = load(sys.argv[1])
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": sys.stdin.read()}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    print(generate(model, tokenizer, prompt=prompt, max_tokens=200, verbose=False))
