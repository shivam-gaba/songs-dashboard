interface Props {
  value: number | null;
  onRate: (stars: number) => void;
  disabled?: boolean;
}

/** Five clickable stars. Clicking star N sets the rating to N. */
export function StarRating({ value, onRate, disabled }: Props) {
  return (
    <span className="stars" role="radiogroup" aria-label="star rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={"star" + (value !== null && n <= value ? " on" : "")}
          disabled={disabled}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          aria-checked={value === n}
          role="radio"
          onClick={() => onRate(n)}
          title={`Rate ${n}`}
        >
          ★
        </button>
      ))}
    </span>
  );
}
