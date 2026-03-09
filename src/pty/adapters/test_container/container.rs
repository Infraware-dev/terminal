//! Container builder for debian latest slim container image.

use bollard::Docker;
use bollard::config::ContainerCreateBody;
use bollard::query_parameters::{
    CreateContainerOptionsBuilder, CreateImageOptionsBuilder, RemoveContainerOptionsBuilder,
};
use futures::StreamExt;

/// Builder for creating and managing a Debian container using [bollard](https://docs.rs/bollard/latest/bollard/).
///
/// The container runs `sleep infinity` as its main process, keeping it alive
/// indefinitely. Individual bash sessions are created via exec.
pub struct Container {
    pub(super) docker: Docker,
    pub(super) name: String,
}

impl Container {
    /// Sets up a Debian container using bollard and returns a handle to it.
    ///
    /// The container starts with `sleep infinity` as entrypoint; individual
    /// bash sessions must be spawned via [`super::SharedContainer::exec_bash`].
    ///
    /// ## Summary flow
    ///
    /// ```text
    ///   connect_with_local_defaults()
    ///           │
    ///      create_image()          ← pull debian:bookworm-slim
    ///           │
    ///      create_container()      ← cmd=["sleep","infinity"]
    ///           │
    ///      start_container()
    /// ```
    pub async fn setup() -> anyhow::Result<Container> {
        let docker = Docker::connect_with_local_defaults()?;
        let name = format!("infraware_{}", uuid::Uuid::new_v4());
        let container = Container { docker, name };
        container.pull_image().await?;
        container.create_container().await?;
        container.start_container().await?;

        Ok(container)
    }

    /// Stops and removes the container to clean up resources after use.
    ///
    /// Stop is best-effort: even if the stop call fails (e.g., container
    /// already exited or a transient network error), removal is always
    /// attempted with `force(true)` which tells Docker to kill and remove
    /// in one shot.
    pub async fn stop(&self) -> anyhow::Result<()> {
        tracing::debug!("Stopping container {}", self.name);
        if let Err(e) = self.docker.stop_container(&self.name, None).await {
            tracing::debug!(
                "Stop request for container {} returned error (will still attempt removal): {e}",
                self.name
            );
        } else {
            tracing::debug!("Stopped container {}", self.name);
        }

        let opts = RemoveContainerOptionsBuilder::default().force(true).build();
        tracing::debug!("Removing container {} with options: {:?}", self.name, opts);
        self.docker.remove_container(&self.name, Some(opts)).await?;
        tracing::debug!("Removed container {}", self.name);

        Ok(())
    }

    /// Create the container image by pulling it from the registry if not already present.
    async fn pull_image(&self) -> anyhow::Result<()> {
        let options = CreateImageOptionsBuilder::default()
            .from_image("debian")
            .tag("bookworm-slim")
            .build();
        tracing::debug!("Pulling Debian image image: {options:?}");
        let mut pull_stream = self.docker.create_image(Some(options), None, None);

        let mut image_info = None;
        while let Some(token) = pull_stream.next().await {
            let info = token?;
            image_info = Some(info);
            tracing::debug!("Pulling image... progress: {image_info:?}");
        }
        let Some(image_info) = image_info else {
            return Err(anyhow::anyhow!(
                "Failed to pull image: no information received"
            ));
        };
        tracing::debug!("Image pulled; image info: {image_info:?}");

        Ok(())
    }

    /// Create the container with `sleep infinity` as the idle entrypoint.
    ///
    /// The container stays alive indefinitely; individual bash sessions are
    /// created via `docker exec`.
    async fn create_container(&self) -> anyhow::Result<()> {
        tracing::debug!("Creating Container: {}", self.name);

        let options = CreateContainerOptionsBuilder::default()
            .name(&self.name)
            .build();

        let config = ContainerCreateBody {
            image: Some("debian:bookworm-slim".to_string()),
            cmd: Some(vec!["sleep".to_string(), "infinity".to_string()]),
            ..Default::default()
        };

        self.docker.create_container(Some(options), config).await?;
        tracing::debug!("Created container: {}", self.name);
        Ok(())
    }

    /// Start the container so that exec sessions can be spawned inside it.
    async fn start_container(&self) -> anyhow::Result<()> {
        tracing::debug!("Starting container: {}", self.name);
        self.docker.start_container(&self.name, None).await?;
        tracing::debug!("Started container: {}", self.name);

        Ok(())
    }
}
