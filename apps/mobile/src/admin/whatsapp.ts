/** Numero in formato wa.me: solo cifre, con il prefisso italiano (39) se manca. */
export function whatsappUrl(phone: string): string {
  const trimmed = phone.trim();
  const digits = trimmed.replace(/[^0-9]/g, "");
  const international = trimmed.startsWith("+") || digits.startsWith("00");
  const full = international ? digits.replace(/^00/, "") : `39${digits}`;
  return `https://wa.me/${full}`;
}
