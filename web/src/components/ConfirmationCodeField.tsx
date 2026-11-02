/** El código tiene 6 dígitos; los espacios que copian algunas aplicaciones no cuentan. */
export function isConfirmationCode(value: string) {
  return /^\d{6}$/.test(value.replace(/\s/g, ""));
}

interface Props {
  value: string;
  onChange(value: string): void;
  disabled?: boolean;
  label?: string;
}

/**
 * Código de 6 dígitos de la aplicación autenticadora. Superadmin y admin lo
 * escriben al ingresar y antes de cambiar cuentas o grupos.
 */
export function ConfirmationCodeField({ value, onChange, disabled = false, label = "Código de tu aplicación autenticadora" }: Props) {
  return <label>{label}
    <input inputMode="numeric" autoComplete="one-time-code" maxLength={7} required disabled={disabled}
      value={value} onChange={(event) => onChange(event.target.value.replace(/[^\d ]/g, ""))} />
  </label>;
}
