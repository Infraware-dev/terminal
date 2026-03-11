//! Docker container lifecycle management.
//!
//! Provides [`Container`] for creating and managing Docker containers via
//! [bollard](https://docs.rs/bollard/latest/bollard/). Used by both the
//! test-container and arena adapters.

use bollard::Docker;
use bollard::config::ContainerCreateBody;
use bollard::query_parameters::{
    CreateContainerOptionsBuilder, CreateImageOptionsBuilder, RemoveContainerOptionsBuilder,
};
use futures::StreamExt;

use super::parse_image_ref;

/// Configuration for creating a Docker container.
#[derive(Debug, Clone)]
pub struct ContainerConfig {
    /// Full image reference (`image:tag`).
    pub image_ref: String,
    /// Command to run inside the container. When `None`, the image's default
    /// `CMD`/`ENTRYPOINT` is used.
    pub cmd: Option<Vec<String>>,
    /// Allocate a TTY for the container's main process.
    pub tty: bool,
    /// Keep stdin open for the container's main process.
    pub open_stdin: bool,
}

/// Handle to a running Docker container.
///
/// Created via [`Container::setup`] with a [`ContainerConfig`].
/// The container is not automatically cleaned up on drop; call [`stop`](Self::stop)
/// explicitly (or use [`super::SharedContainer`] which handles cleanup).
pub struct Container {
    pub(super) docker: Docker,
    pub(super) name: String,
    pub(super) image_ref: String,
}

impl std::fmt::Debug for Container {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Container")
            .field("name", &self.name)
            .field("image_ref", &self.image_ref)
            .finish_non_exhaustive()
    }
}

impl Container {
    /// Pulls the image, creates the container, and starts it.
    pub async fn setup(config: ContainerConfig) -> anyhow::Result<Self> {
        let docker = Docker::connect_with_local_defaults()?;
        let name = format!("infraware_{}", uuid::Uuid::new_v4());
        let container = Self {
            docker,
            name,
            image_ref: config.image_ref.clone(),
        };

        let (repo, tag) = parse_image_ref(&config.image_ref);
        container.pull_image(repo, tag).await?;
        container.create_container(&config).await?;
        container.start_container().await?;

        Ok(container)
    }

    /// Stops and removes the container.
    ///
    /// Stop is best-effort: even if the stop call fails, removal is always
    /// attempted with `force(true)`.
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

    async fn pull_image(&self, image: &str, tag: &str) -> anyhow::Result<()> {
        let options = CreateImageOptionsBuilder::default()
            .from_image(image)
            .tag(tag)
            .build();
        tracing::debug!("Pulling container image: {options:?}");
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

    async fn create_container(&self, config: &ContainerConfig) -> anyhow::Result<()> {
        tracing::debug!("Creating container: {}", self.name);

        let options = CreateContainerOptionsBuilder::default()
            .name(&self.name)
            .build();

        let body = ContainerCreateBody {
            image: Some(self.image_ref.clone()),
            cmd: config.cmd.clone(),
            tty: Some(config.tty),
            open_stdin: Some(config.open_stdin),
            ..Default::default()
        };

        self.docker.create_container(Some(options), body).await?;
        tracing::debug!("Created container: {}", self.name);
        Ok(())
    }

    async fn start_container(&self) -> anyhow::Result<()> {
        tracing::debug!("Starting container: {}", self.name);
        self.docker.start_container(&self.name, None).await?;
        tracing::debug!("Started container: {}", self.name);
        Ok(())
    }
}
