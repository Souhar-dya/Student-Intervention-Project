import type { ButtonHTMLAttributes } from "react";
import { LoaderCircle } from "lucide-react";
import { cva, type VariantProps } from "class-variance-authority";
import { twMerge } from "tailwind-merge";

const buttonStyles = cva(
  "sharp-corners inline-flex min-h-11 items-center justify-center border px-4 font-sans text-xs font-bold uppercase tracking-widest transition-all duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        primary:
          "border-transparent bg-ink text-newsprint hover:border-ink hover:bg-newsprint hover:text-ink disabled:hover:border-transparent disabled:hover:bg-ink disabled:hover:text-newsprint",
        secondary:
          "border-ink bg-transparent text-ink hover:bg-ink hover:text-newsprint disabled:hover:bg-transparent disabled:hover:text-ink",
      },
      size: {
        sm: "min-h-11 px-3",
        md: "min-h-12 px-5",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonStyles> & {
    isLoading?: boolean;
    loadingLabel?: string;
  };

export function Button({
  children,
  className,
  disabled,
  isLoading = false,
  loadingLabel,
  type = "button",
  variant,
  size,
  ...props
}: ButtonProps) {
  return (
    <button
      aria-busy={isLoading}
      className={twMerge(buttonStyles({ variant, size }), className)}
      disabled={disabled || isLoading}
      type={type}
      {...props}
    >
      {isLoading ? <LoaderCircle aria-hidden="true" className="mr-2 h-4 w-4 animate-spin" /> : null}
      <span>{isLoading && loadingLabel ? loadingLabel : children}</span>
    </button>
  );
}
