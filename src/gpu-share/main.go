package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	pluginapi "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
)

const (
	resourceName = "amd.com/gpu-share"
	socketName   = "amd-gpu-share.sock"
)

type plugin struct {
	shares   int
	instance string
}

func (p *plugin) GetDevicePluginOptions(ctx context.Context, e *pluginapi.Empty) (*pluginapi.DevicePluginOptions, error) {
	return &pluginapi.DevicePluginOptions{}, nil
}

func (p *plugin) ListAndWatch(e *pluginapi.Empty, s pluginapi.DevicePlugin_ListAndWatchServer) error {
	log.Printf("ListAndWatch started (instance=%s shares=%d)", p.instance, p.shares)
	devs := make([]*pluginapi.Device, 0, p.shares)
	for i := 0; i < p.shares; i++ {
		devs = append(devs, &pluginapi.Device{
			ID:     fmt.Sprintf("%s-%d", p.instance, i),
			Health: pluginapi.Healthy,
		})
	}

	// Must keep the stream open; kubelet treats stream termination as plugin failure.
	if err := s.Send(&pluginapi.ListAndWatchResponse{Devices: devs}); err != nil {
		return err
	}

	t := time.NewTicker(30 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-s.Context().Done():
			return nil
		case <-t.C:
			// Periodic refresh; also acts as keepalive.
			if err := s.Send(&pluginapi.ListAndWatchResponse{Devices: devs}); err != nil {
				return err
			}
		}
	}
}

func (p *plugin) Allocate(ctx context.Context, req *pluginapi.AllocateRequest) (*pluginapi.AllocateResponse, error) {
	// We’re not handing out a real device; this is just scheduler-gating.
	// You will mount /dev/dri in your pod spec to access Vulkan.
	for i, cr := range req.ContainerRequests {
		log.Printf("Allocate request (instance=%s container=%d deviceIDs=%v)", p.instance, i, cr.DevicesIDs)
	}
	// Important: requesting an extended resource only affects scheduling unless the device
	// plugin also returns DeviceSpecs. Kubelet uses DeviceSpecs to allow device cgroup access
	// (and optionally mount device nodes). This is why requesting amd.com/gpu works while
	// amd.com/gpu-share would otherwise not.

	deviceSpecs := make([]*pluginapi.DeviceSpec, 0, 16)

	// /dev/kfd is required for ROCm/HSA on AMD GPUs.
	if _, err := os.Stat("/dev/kfd"); err == nil {
		deviceSpecs = append(deviceSpecs, &pluginapi.DeviceSpec{
			HostPath:      "/dev/kfd",
			ContainerPath: "/dev/kfd",
			Permissions:   "rwm",
		})
	}

	// Render nodes (Vulkan/OpenCL) are typically /dev/dri/renderD*.
	renderNodes, _ := filepath.Glob("/dev/dri/renderD*")
	for _, pth := range renderNodes {
		deviceSpecs = append(deviceSpecs, &pluginapi.DeviceSpec{
			HostPath:      pth,
			ContainerPath: pth,
			Permissions:   "rwm",
		})
	}

	// Some stacks still touch /dev/dri/card*.
	cardNodes, _ := filepath.Glob("/dev/dri/card*")
	for _, pth := range cardNodes {
		deviceSpecs = append(deviceSpecs, &pluginapi.DeviceSpec{
			HostPath:      pth,
			ContainerPath: pth,
			Permissions:   "rwm",
		})
	}

	log.Printf("Allocate will return %d DeviceSpecs: %v", len(deviceSpecs), func() []string {
		out := make([]string, 0, len(deviceSpecs))
		for _, d := range deviceSpecs {
			out = append(out, d.HostPath)
		}
		return out
	}())

	resp := &pluginapi.AllocateResponse{}
	for range req.ContainerRequests {
		resp.ContainerResponses = append(resp.ContainerResponses, &pluginapi.ContainerAllocateResponse{
			Devices: deviceSpecs,
		})
	}
	return resp, nil
}

func (p *plugin) PreStartContainer(ctx context.Context, req *pluginapi.PreStartContainerRequest) (*pluginapi.PreStartContainerResponse, error) {
	return &pluginapi.PreStartContainerResponse{}, nil
}

func (p *plugin) GetPreferredAllocation(ctx context.Context, req *pluginapi.PreferredAllocationRequest) (*pluginapi.PreferredAllocationResponse, error) {
	// No special allocation preference; let kubelet decide.
	return &pluginapi.PreferredAllocationResponse{}, nil
}

func main() {
	shares, _ := strconv.Atoi(os.Getenv("GPU_SHARES"))
	if shares <= 0 {
		shares = 8
	}

	instance := os.Getenv("GPU_SHARE_INSTANCE")
	if instance == "" {
		// Unique-ish per process; helps kubelet drop stale allocations when lots of pods failed admission.
		instance = fmt.Sprintf("%d", time.Now().UnixNano())
	}

	socketPath := pluginapi.DevicePluginPath + socketName
	_ = os.Remove(socketPath)

	l, err := net.Listen("unix", socketPath)
	if err != nil {
		log.Fatalf("listen %s: %v", socketPath, err)
	}

	s := grpc.NewServer()
	pluginapi.RegisterDevicePluginServer(s, &plugin{shares: shares, instance: instance})

	go func() {
		log.Printf("serving on %s (shares=%d)", socketPath, shares)
		if err := s.Serve(l); err != nil {
			log.Fatalf("serve: %v", err)
		}
	}()

	// Register with kubelet
	// KubeletSocket from k8s.io/kubelet is a raw filesystem path. grpc.NewClient needs a
	// resolvable target; use unix:/// to force the unix socket resolver.
	conn, err := grpc.NewClient(
		"unix:///"+pluginapi.KubeletSocket,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		log.Fatalf("dial kubelet: %v", err)
	}
	defer conn.Close()

	client := pluginapi.NewRegistrationClient(conn)
	_, err = client.Register(context.Background(), &pluginapi.RegisterRequest{
		Version:      pluginapi.Version,
		Endpoint:     socketName,
		ResourceName: resourceName,
	})
	if err != nil {
		log.Fatalf("register: %v", err)
	}

	log.Printf("registered resource %s", resourceName)
	select {}
}
