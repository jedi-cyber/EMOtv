import { ButtonLink } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { paths } from "../routes/paths";

/**
 * Juegos: la actividad de dibujo y una versión de prueba de cada juego, que no
 * crean una sesión, no usan la cámara ni guardan datos. «Jugar con la cámara» lleva
 * al Analizador con ese juego elegido: ahí es una sesión, con su autorización.
 */
export function GamesPage() {
  return <section>
    <PageHeader title="Juegos" description="Prueba los juegos antes de ponerlos en un protocolo. La prueba no crea una sesión, no usa la cámara y no guarda nada." />
    <p className="muted">«Jugar con la cámara» abre el Analizador con el juego elegido: la persona responde poniendo la cara y la cámara marca la opción. Es una sesión, con su autorización y su código.</p>
    <div className="card-grid">
      <article className="card">
        <h2>Dibuja una cara</h2>
        <p>Elige imágenes para que la persona dibuje una cara a partir de cada una, o dibuja sin imagen. No crea una sesión, no usa la cámara y no guarda el dibujo.</p>
        <ButtonLink variant="primary" to={paths.drawing}>Actividad de dibujo</ButtonLink>
      </article>
      <article className="card">
        <h2>Empareja la emoción</h2>
        <p>Se muestra una cara y la persona elige el nombre de su emoción. Versión de prueba de tres rondas, con caras dibujadas.</p>
        <div className="inline-actions">
          <ButtonLink variant="primary" to={paths.game("matching")}>Jugar la prueba</ButtonLink>
          <ButtonLink variant="secondary" to={paths.analysisWithCameraGame("matching")}>Jugar con la cámara</ButtonLink>
        </div>
      </article>
      <article className="card">
        <h2>Busca la misma emoción</h2>
        <p>Se muestra una cara arriba y la persona busca, entre otras caras, la que muestra la misma emoción. Versión de prueba de tres rondas.</p>
        <div className="inline-actions">
          <ButtonLink variant="primary" to={paths.game("similar")}>Jugar la prueba</ButtonLink>
          <ButtonLink variant="secondary" to={paths.analysisWithCameraGame("similar")}>Jugar con la cámara</ButtonLink>
        </div>
      </article>
    </div>
  </section>;
}
