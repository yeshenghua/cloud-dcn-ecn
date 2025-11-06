package dcn;

import inet.node.inet.Router;
import inet.node.inet.StandardHost;
import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import ned.DatarateChannel;

// Parametric channel (was Eth10G) now named EthChan with overridable datarate/delay.
channel EthChan extends DatarateChannel
{
    parameters:
        datarate @unit(bps) = default(10Gbps);
        delay @unit(s) = default(2us);
}

network SmallLeafSpine
{
    parameters:
        int hostsPerLeaf = default(3);
    submodules:
        configurator: Ipv4NetworkConfigurator { parameters: @display("p=60,40"); }
        spine[2]: Router { parameters: @display("p=350,80"); }
        leaf[4]:  Router { parameters: @display("p=150,180;i=block/router"); }
        host[4*hostsPerLeaf]: StandardHost { parameters: @display("i=device/laptop"); }
    connections allowunconnected:
        // leaf <-> all spines（单层 for，里头直接写两条连接）
        for i=0..3 {
            leaf[i].pppg++ <--> EthChan <--> spine[0].pppg++;
            leaf[i].pppg++ <--> EthChan <--> spine[1].pppg++;
        }
        // hosts <-> 对应的 leaf（用 k/hostsPerLeaf 计算所属 leaf）
        for k=0..(4*hostsPerLeaf-1) {
            host[k].pppg++ <--> EthChan <--> leaf[int(k/hostsPerLeaf)].pppg++;
        }
}
