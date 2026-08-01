import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

/** Minimal runtime-only smoke model; it contains no photonic physics claim. */
public final class ComsolRuntimeSmoke {
  private ComsolRuntimeSmoke() {}

  public static Model run() {
    Model model = ModelUtil.create("Model");
    model.label("COMSOL Runtime Smoke");
    model.comments(
        "Runtime activation only: no geometry, physics, mesh, study, or acceptance claim.");
    return model;
  }

  public static void main(String[] args) {
    run();
  }
}
