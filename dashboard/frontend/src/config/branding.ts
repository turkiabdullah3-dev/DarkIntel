import faviconPath from '../assets/branding/favicon.png'
import iconPath from '../assets/branding/logo-mark.webp'
import logoPath from '../assets/branding/logo.webp'

export const branding = { productName: 'DarkIntel', productShortName: 'DI',
  productTagline: 'CTI & OSINT Investigation Platform', ownerName: 'Turki Almuraykhi',
  logoPath, iconPath, faviconPath } as const

export function applyBrandingMetadata() {
  document.title = branding.productName
  document.querySelector('meta[name="description"]')?.setAttribute('content',
    `${branding.productName} — ${branding.productTagline}`)
  document.querySelector<HTMLLinkElement>('link[rel="icon"]')?.setAttribute('href', branding.faviconPath)
}
